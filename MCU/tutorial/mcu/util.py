import cv2  
import base64
from openai import OpenAI
import os
import json

from datetime import datetime
from pathlib import Path

root_dir = Path(__file__).resolve().parents[2]

def extract_info(yaml_content, filename):
    lines = yaml_content.splitlines()
    commands = []
    text = ''

    for line in lines:
        if line.startswith('-'):
            command = line.strip('- ').strip()
            commands.append(command)
        elif line.startswith('text:'):
            text = line.strip('text: ').strip()

    task_name = filename[:-5].replace('_', ' ')
    return task_name, commands, text

def get_tasks(difficulty: str, task_list: list[str]|None=None, num_tasks: int|None=None) -> list[str]:
    # Resolve task configs directory relative to this file's project root
    task_dir = root_dir / 'MCU_benchmark' / 'task_configs' / difficulty
    if not task_dir.exists():
        raise FileNotFoundError(f"Task configs directory not found: {task_dir}")
    all_task_files = [p.name for p in task_dir.iterdir() if p.suffix == '.yaml']
    
    if task_list:
        task_files = [f"{task.replace(' ', '_')}.yaml" for task in task_list if f"{task.replace(' ', '_')}.yaml" in all_task_files]
        if len(task_files) == 0:
            print("No matching task names found. Using all tasks.")
            task_files = all_task_files
    else: 
        task_files = all_task_files
        
    if num_tasks:
        task_files = task_files[:num_tasks]
    
    tasks = []
    for filename in task_files:
        file_path = task_dir / filename
        with open(file_path, 'r', encoding='utf-8') as file:
            yaml_content = file.read()
        task_name, commands, text = extract_info(yaml_content, filename)
        tasks.append((task_name, commands, text))
    
    return tasks

def fetch(query, model='gpt-4o'): # gpt4
    print(f'fetching {model} ...')
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable not set")
    client = OpenAI(api_key=api_key)
    completion = client.chat.completions.create(
        model=model,
        messages=query,
        temperature=0.7
    )
    res = completion.choices[0].message.content
    return res

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
    base64Frames = []
    while video.isOpened():
        success, frame = video.read()
        if not success:
            break
        # frame = cv2.resize(orig_frame, (224, 224))
        if not success:
            break
        _, buffer = cv2.imencode(".jpg", frame)
        base64Frames.append(base64.b64encode(buffer).decode("utf-8"))

    video.release()

    base64Frames1 = base64Frames[0::25]
    print(len(base64Frames1), "frames read.")
    if (len(base64Frames1) > 60):
        base64Frames1 = base64Frames[0::70]
        
    return base64Frames1

def assess_video(task, rule_file, frames, video_path):
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
    result = save_data_json(response, task, video_path)
    return result

def save_data_json(response: str, task: str, video_path: str) -> dict:
    result = {}
    keys_to_extract = [  
        "Task Progress",  
        "Action Control",  
        "Error Recognition and Correction",  
        "Creative Attempts",  
        "Task Completion Efficiency",  
        "Material Selection and Usage"  
    ]  

    for line in response.strip().split('\n'):  
        for key in keys_to_extract:  
            if line.startswith(f'- {key}: '):   
                value = (line.split(': ', 1)[1].strip()) 
                
                if value: 
                    result[key] = value  
                    break  
                
    result['video_path'] = video_path
    result['task'] = task
    
    video_path_obj = Path(video_path)
    try:
        relative_path = video_path_obj.relative_to(root_dir / "record")
        difficulty = relative_path.parts[0]
        date = relative_path.parts[1]
    except (ValueError, IndexError):
        difficulty = "unknown"
        date = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    result_dir = root_dir / "_eval_result" / difficulty / date
    result_dir.mkdir(parents=True, exist_ok=True)
    
    out_file = result_dir / f"{task.replace(' ', '_')}.json"
    with open(out_file, 'w') as f:
        json.dump(result, f, indent=4)

    return result 
