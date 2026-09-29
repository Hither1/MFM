"""
Progress Evaluator - Green Agent based milestone progress assessment

Uses GPT-4o (VLM) to evaluate the progress toward completing a milestone
by analyzing video clips of agent behavior.

Date: 2026-01-14
"""

import os
import cv2
import base64
import json
import re
from pathlib import Path
from openai import OpenAI


def process_video(video_path: str, sample_interval: int = 25, max_frames: int = 60) -> list[str]:
    """
    Extract frames from video and encode as base64.

    Args:
        video_path: Path to the video file
        sample_interval: Sample every N frames (default: 25)
        max_frames: Maximum number of frames to extract (default: 60)

    Returns:
        list[str]: List of base64-encoded frames
    """
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video not found: {video_path}")

    video = cv2.VideoCapture(video_path)
    base64_frames = []

    while video.isOpened():
        success, frame = video.read()
        if not success:
            break
        _, buffer = cv2.imencode(".jpg", frame)
        base64_frames.append(base64.b64encode(buffer).decode("utf-8"))

    video.release()

    # Sample frames
    sampled_frames = base64_frames[0::sample_interval]
    print(f"Extracted {len(sampled_frames)} frames from video")

    # Limit to max_frames
    if len(sampled_frames) > max_frames:
        # Resample if too many frames
        new_interval = len(base64_frames) // max_frames
        sampled_frames = base64_frames[0::new_interval]
        print(f"Resampled to {len(sampled_frames)} frames")

    return sampled_frames


def create_progress_evaluation_prompt(
    task_name: str,
    milestone_identity: str,
    milestone_cfg: dict,
    criteria_file: str
) -> str:
    """
    Create a specialized prompt for evaluating milestone progress.

    Args:
        task_name: Name of the task (e.g., "mine_diamond_from_scratch")
        milestone_identity: Identity of the milestone being evaluated
        milestone_cfg: Configuration dict for the milestone
        criteria_file: Path to criteria file

    Returns:
        str: Formatted prompt for GPT-4o
    """
    # Read criteria file
    if not os.path.exists(criteria_file):
        raise FileNotFoundError(f"Criteria file not found: {criteria_file}")

    with open(criteria_file, 'r', encoding='utf-8') as f:
        criteria = f.read()

    # Extract milestone description
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


def extract_task_progress_score(response: str) -> float:
    """
    Extract Task Progress score from GPT-4o response.

    Args:
        response: GPT-4o response text

    Returns:
        float: Score from 0-10
    """
    # Try to find "Score: X" pattern
    match = re.search(r'Score:\s*(\d+(?:\.\d+)?)', response, re.IGNORECASE)
    if match:
        score = float(match.group(1))
        # Clamp to 0-10 range
        return max(0.0, min(10.0, score))

    # Try to find just a number after "Task Progress"
    lines = response.split('\n')
    for i, line in enumerate(lines):
        if 'Task Progress' in line or 'score' in line.lower():
            # Look in the next few lines
            for j in range(i, min(i + 5, len(lines))):
                num_match = re.search(r'(\d+(?:\.\d+)?)', lines[j])
                if num_match:
                    score = float(num_match.group(1))
                    return max(0.0, min(10.0, score))

    # Default to 0 if can't parse
    print(f"Warning: Could not parse score from response, defaulting to 0")
    return 0.0


def assess_progress_clip(
    task_name: str,
    milestone_identity: str,
    milestone_cfg: dict,
    video_path: str,
    criteria_file: str,
    model: str = 'gpt-4o'
) -> dict:
    """
    Evaluate progress toward a specific milestone using GPT-4o.

    Args:
        task_name: Name of the task
        milestone_identity: Identity of the milestone being evaluated
        milestone_cfg: Configuration dict for the milestone
        video_path: Path to video clip showing progress
        criteria_file: Path to criteria file
        model: OpenAI model to use (default: gpt-4o)

    Returns:
        dict: {
            'milestone_identity': str,
            'score_0_10': float,  # Raw score from 0-10
            'progress_0_1': float,  # Normalized progress from 0-1
            'evidence': str,  # Evidence from evaluation
            'raw_response': str  # Full GPT-4o response
        }
    """
    print(f"\n{'='*60}")
    print(f"Evaluating progress on milestone: {milestone_identity}")
    print(f"Video: {video_path}")
    print(f"{'='*60}\n")

    # 1. Extract video frames
    frames = process_video(video_path)

    # 2. Create evaluation prompt
    prompt = create_progress_evaluation_prompt(
        task_name=task_name,
        milestone_identity=milestone_identity,
        milestone_cfg=milestone_cfg,
        criteria_file=criteria_file
    )

    # 3. Build query for GPT-4o
    query = [
        {
            "role": "system",
            "content": prompt
        },
        {
            "role": "user",
            "content": "Here are the image frames of the video clip:"
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{frame}"
                    }
                }
                for frame in frames
            ]
        }
    ]

    # 4. Call GPT-4o
    print(f"Calling {model} for evaluation...")
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable not set")

    client = OpenAI(api_key=api_key)
    completion = client.chat.completions.create(
        model=model,
        messages=query,
        temperature=0.7
    )
    response = completion.choices[0].message.content

    print(f"\nGPT-4o Response:\n{response}\n")

    # 5. Extract score
    score_0_10 = extract_task_progress_score(response)
    progress_0_1 = score_0_10 / 10.0

    # 6. Extract evidence (lines after "evidence:")
    evidence = ""
    lines = response.split('\n')
    for i, line in enumerate(lines):
        if 'evidence' in line.lower():
            # Get the content after "evidence:"
            evidence_match = re.search(r'evidence:?\s*(.+)', line, re.IGNORECASE)
            if evidence_match:
                evidence = evidence_match.group(1).strip()
                # If it continues on next lines, grab those too
                for j in range(i + 1, min(i + 5, len(lines))):
                    if lines[j].strip() and not lines[j].strip().startswith('Score'):
                        evidence += ' ' + lines[j].strip()
                    else:
                        break
                break

    result = {
        'milestone_identity': milestone_identity,
        'score_0_10': score_0_10,
        'progress_0_1': progress_0_1,
        'evidence': evidence,
        'raw_response': response
    }

    print(f"Progress Score: {score_0_10}/10 = {progress_0_1:.2f}")
    print(f"Evidence: {evidence}\n")

    return result


if __name__ == '__main__':
    # Example usage
    import argparse

    parser = argparse.ArgumentParser(description='Evaluate milestone progress from video clip')
    parser.add_argument('--video', type=str, required=True, help='Path to video clip')
    parser.add_argument('--task', type=str, required=True, help='Task name')
    parser.add_argument('--milestone', type=str, required=True, help='Milestone identity')
    parser.add_argument('--criteria', type=str, required=True, help='Path to criteria file')

    args = parser.parse_args()

    # Simple milestone config for testing
    milestone_cfg = {
        'identity': args.milestone,
        'event': 'test',
        'objects': ['test_object']
    }

    result = assess_progress_clip(
        task_name=args.task,
        milestone_identity=args.milestone,
        milestone_cfg=milestone_cfg,
        video_path=args.video,
        criteria_file=args.criteria
    )

    print(json.dumps(result, indent=2))
