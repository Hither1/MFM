import sys
import cv2  
import base64
from openai import OpenAI
import os
import json
import yaml
import time
import re

from datetime import datetime
from pathlib import Path


root_dir = Path(__file__).resolve().parents[1]

def extract_info(yaml_content: str, filename: str) -> tuple:
    data = yaml.safe_load(yaml_content)
    
    commands = data.get('custom_init_commands', None)
    text = data.get('text', '')
    reward_cfg = data.get('reward_cfg', None)
    milestone_reward_cfg = data.get('milestone_reward_cfg', None)
    
    task = filename[:-5]
    return task, commands, text, reward_cfg, milestone_reward_cfg

def get_tasks(task_category: str) -> list[tuple]:
    # Resolve task configs directory relative to this file's project root
    tasks_dir = root_dir / 'MCU_benchmark' / 'task_configs' / 'tasks' / task_category
    if not tasks_dir.exists():
        raise FileNotFoundError(f"Task configs directory not found: {tasks_dir}")
    
    task_files = []
    for task_file in tasks_dir.glob('*.yaml'):
        task_files.append(task_file)

    # Parse each task file
    tasks = []
    for task_file in task_files:
        with open(task_file, 'r', encoding='utf-8') as file:
            yaml_content = file.read()
        task, commands, text, reward_cfg, milestone_reward_cfg = extract_info(yaml_content, task_file.name)
        tasks.append((task, commands, text, reward_cfg, milestone_reward_cfg))
    
    return tasks

def fetch(query: list[dict], model: str = 'gpt-4o') -> str:  # gpt4
    print(f'fetching {model} ...')
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable not set")
    
    client = OpenAI(api_key=api_key)
    
    max_attempts = 3
    for attempt in range(max_attempts):
        try:
            completion = client.chat.completions.create(
                model=model,
                messages=query,
                temperature=0,
                top_p=1,
                seed=42,
                frequency_penalty=0,
                presence_penalty=0
            )
            return completion.choices[0].message.content
        except Exception as e:
            print(f"API call failed (attempt {attempt + 1}/{max_attempts}): {e}")
            if attempt < max_attempts - 1:
                time.sleep(2 ** attempt)  
            else:
                raise

def process_video(video_path: str) -> list[str]:
    """Extract frames from video and encode as base64.
    
    Args:
        video_path: Path to the video file
        
    Returns:
        list[str]: List of base64-encoded frames
    """
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video not found: {video_path}")
    
    video = cv2.VideoCapture(video_path)
    total_frames = int(video.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = int(video.get(cv2.CAP_PROP_FPS))
    
    # Adaptive sampling rate
    if total_frames < 60 * 20:
        sample_rate = 20  # Every 20 frames (~1 sec at 20fps)
    else:
        sample_rate = 60
    
    base64Frames = []
    frame_count = 0
    
    while video.isOpened():
        success, frame = video.read()
        if not success:
            break
        
        if frame_count % sample_rate == 0:
            _, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
            base64Frames.append(base64.b64encode(buffer).decode("utf-8"))
        
        frame_count += 1
    
    video.release()
    print(f"{len(base64Frames)} frames sampled from {total_frames} total frames.")
    return base64Frames

def assess_video(task: str, rule_file: str, frames: list[str], video_path: str) -> dict:
    """Assess video and return detailed evaluation.
    
    Returns:
        dict: {
            'final_score': float,
            'breakdown': dict,  # Individual criterion scores
            'weights': dict     # Applied weights
        }
    """
    prompt_dir = root_dir / 'MCU_benchmark' / 'auto_eval' / 'prompt'
    prompt_file = prompt_dir / 'single_rating_prompt.txt'
    if not prompt_file.exists():
        raise FileNotFoundError(f"Prompt file not found: {prompt_file}")
    
    with open(prompt_file, 'r', encoding='utf-8') as file:  
        system_content = file.read()
    
    if not os.path.exists(rule_file):
        raise FileNotFoundError(f"Rule file not found: {rule_file}")
        
    with open(rule_file, 'r', encoding='utf-8') as file:  
        grading_rule = file.read()
        
    query = [
        {
        "role": "system",
        "content": system_content
        },
        {
        "role": "user", "content":  
        f'The task name is ' + task + ' '
        + f'You should follow the following grading criteria to score the performance of agents in videos' + grading_rule +'\n'
        + f'Here are the image frames of the video '
        }]

    query.append(
        {
            "role": "user", 
            "content": [
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{frame}"
                    },
                } for frame in frames
            ]
        }
    )

    response = fetch(query)
    result = save_data_json(response, task, video_path, grading_rule)
    return result

def save_data_json(response: str, task: str, video_path: str, grading_rule: str = "") -> float:
    result = {}
    keys_to_extract = [  
        "Task Progress",  
        "Action Control",  
        "Error Recognition and Correction",  
        "Creative Attempts",  
        "Task Completion Efficiency",  
        "Material Selection and Usage"  
    ]  

    result['task'] = task
    result['video_path'] = video_path
    
    # Check which criteria are marked as "Not applicable" in the rule file
    criterias = set(keys_to_extract)
    if grading_rule:
        for key in keys_to_extract:
            # Check if the criterion section contains "Not applicable"
            if f"**{key}:" in grading_rule:
                section_start = grading_rule.find(f"**{key}:")
                section_end = grading_rule.find("\n\n**", section_start)
                if section_end == -1:
                    section_end = len(grading_rule)
                section = grading_rule[section_start:section_end]
                if "Not applicable" in section or "not applicable" in section:
                    criterias.discard(key)
                    print(f"Excluding '{key}' from scoring (marked as not applicable)")
    
    scores = {}
    for line in response.strip().split('\n'):
        for key in keys_to_extract:
            if line.startswith(f'- {key}: '):
                try:
                    value = line.split(': ', 1)[1].strip()
                    scores[key] = float(value)
                    break
                except (ValueError, IndexError):
                    pass
            elif line.startswith(f'{key}: '):
                try:
                    value = line.split(': ', 1)[1].strip()
                    scores[key] = float(value)
                    break
                except (ValueError, IndexError):
                    pass
    
    # Validate all scores are within 0-10 range
    for key in keys_to_extract:
        if key in scores:
            scores[key] = max(0.0, min(10.0, scores[key]))

    result['scores'] = scores
    result['criterias'] = list(criterias)
    result['original_response'] = response
    
    output_dir = os.path.dirname(video_path)
    result_path = os.path.join(output_dir, f"video_eval_result.json")
    with open(result_path, 'w') as f:
        json.dump(result, f, indent=4)

    return {
        'scores': scores,
        'criterias': list(criterias),
    }


def _create_progress_evaluation_prompt(
    task_name: str,
    milestone_identity: str,
    milestone_cfg: dict,
    criteria_file: str
) -> str:
    """Create a specialized prompt for evaluating milestone progress."""
    if not os.path.exists(criteria_file):
        raise FileNotFoundError(f"Criteria file not found: {criteria_file}")

    with open(criteria_file, 'r', encoding='utf-8') as f:
        criteria = f.read()

    event_type = milestone_cfg.get('event', 'unknown')
    objects = milestone_cfg.get('objects', [])

    prompt = f"""You are an expert Minecraft evaluator.

TASK: {task_name}
CURRENT MILESTONE TARGET: {milestone_identity}

Milestone Details:
- Event Type: {event_type}
- Target Objects: {', '.join(objects)}
- Description: {milestone_cfg}

IMPORTANT: Evaluate ONLY the progress toward achieving the specific milestone "{milestone_identity}".
This is NOT the entire task - focus ONLY on this single milestone.

The video clip shows the agent's behavior AFTER completing previous milestones and BEFORE completing this one.
Your job is to assess how much progress the agent has made toward "{milestone_identity}".

Grading Criteria:
{criteria}

**Focus on the "Task Progress" dimension** - specifically for the milestone "{milestone_identity}".

Rating Scale (0-10):
- 0: No progress toward this milestone (agent is not working on it or doing unrelated actions)
- 1-3: Minimal progress (agent is gathering prerequisites or just starting)
- 4-6: Partial progress (agent has made some steps toward the milestone but hasn't completed it)
- 7-9: Significant progress (agent is very close to completing the milestone, almost there)
- 10: Milestone completed (agent has fully achieved {milestone_identity})

Output Format:
Task Progress:
- evidence: [Describe specific actions you observed that show progress toward {milestone_identity}]
Score: [0-10]

Provide ONLY the Task Progress evaluation. Be specific about what you observed."""

    return prompt


def _extract_task_progress_score(response: str) -> float:
    """Extract Task Progress score from GPT-4o response."""
    match = re.search(r'Score:\s*(\d+(?:\.\d+)?)', response, re.IGNORECASE)
    if match:
        score = float(match.group(1))
        return max(0.0, min(10.0, score))

    lines = response.split('\n')
    for i, line in enumerate(lines):
        if 'Task Progress' in line or 'score' in line.lower():
            for j in range(i, min(i + 5, len(lines))):
                number_match = re.search(r'(\d+(?:\.\d+)?)', lines[j])
                if number_match:
                    score = float(number_match.group(1))
                    return max(0.0, min(10.0, score))
    
    return 0.0


def assess_progress_clip(
    task_name: str,
    milestone_identity: str,
    milestone_cfg: dict,
    video_path: str,
    criteria_file: str,
    model: str = 'gpt-4o'
) -> dict:
    """Evaluate progress toward a specific milestone using GPT-4o.
    
    Returns:
        dict: {
            'milestone_identity': str,
            'score_0_10': float,
            'progress_0_1': float,
            'evidence': str,
            'raw_response': str
        }
    """
    # Extract video frames
    frames = process_video(video_path)

    # Create evaluation prompt
    prompt = _create_progress_evaluation_prompt(
        task_name=task_name,
        milestone_identity=milestone_identity,
        milestone_cfg=milestone_cfg,
        criteria_file=criteria_file
    )

    # Build query for GPT-4o
    query = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": "Here are the image frames of the video clip:"},
        {
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{frame}"}
                }
                for frame in frames
            ]
        }
    ]

    # Call GPT-4o
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable not set")

    client = OpenAI(api_key=api_key)
    completion = client.chat.completions.create(
        model=model,
        messages=query,
        temperature=0,
        top_p=1,
        seed=42,
        frequency_penalty=0,
        presence_penalty=0
    )
    response = completion.choices[0].message.content

    # Extract score
    score_0_10 = _extract_task_progress_score(response)
    progress_0_1 = score_0_10 / 10.0

    # Extract evidence
    evidence = ""
    lines = response.split('\n')
    for i, line in enumerate(lines):
        if 'evidence' in line.lower():
            evidence_match = re.search(r'evidence:?\s*(.+)', line, re.IGNORECASE)
            if evidence_match:
                evidence = evidence_match.group(1).strip()
                for j in range(i + 1, min(i + 5, len(lines))):
                    if lines[j].strip() and not lines[j].strip().startswith('Score'):
                        evidence += ' ' + lines[j].strip()
                    else:
                        break
                break

    return {
        'milestone_identity': milestone_identity,
        'score_0_10': score_0_10,
        'progress_0_1': progress_0_1,
        'evidence': evidence,
        'raw_response': response
    }


def evaluate_longterm_result(record_path: Path) -> float:
    """Evaluate long-term task results with continuous scoring.
    
    Args:
        record_path: Output directory containing milestone_tracking.json

    Returns:
        float: Continuous score (completed_milestones + current_progress)
    """
    # Load milestone_tracking.json
    tracking_file = record_path / 'milestone_tracking.json'
    if not tracking_file.exists():
        raise FileNotFoundError(f"Tracking file not found: {tracking_file}")

    with open(tracking_file, 'r') as f:
        tracking_data = json.load(f)

    # Extract completed milestone count
    completed_count = tracking_data['milestones_achieved']
    total_milestones = tracking_data['total_milestones']
    task_name = tracking_data['task']

    # Evaluate current progress
    current_progress = 0.0
    progress_result = None

    if completed_count < total_milestones:
        if 'current_progress_clip' in tracking_data:
            clip_info = tracking_data['current_progress_clip']
            clip_path = Path(clip_info['video_path'])

            if clip_path.exists():
                current_milestone_cfg = clip_info['milestone_cfg']
                milestone_identity = clip_info['milestone_target']

                # Determine criteria file path
                criteria_dir = root_dir / 'MCU_benchmark' / 'auto_eval' / 'criteria_files'
                criteria_file = criteria_dir / f"{task_name}.txt"

                if not criteria_file.exists():
                    criteria_file = criteria_dir / f"{task_name.replace(' ', '_')}.txt"

                if criteria_file.exists():
                    progress_result = assess_progress_clip(
                        task_name=task_name,
                        milestone_identity=milestone_identity,
                        milestone_cfg=current_milestone_cfg,
                        video_path=str(clip_path),
                        criteria_file=str(criteria_file)
                    )
                    current_progress = progress_result['progress_0_1']

    # Calculate final continuous score
    final_score = completed_count + current_progress

    return final_score
