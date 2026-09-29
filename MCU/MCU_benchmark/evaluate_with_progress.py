"""
Continuous Score Evaluation for Long-term Tasks

Evaluates the output from run_longterm_task.py and calculates a continuous score:
    Score = completed_milestones + current_milestone_progress (0-1)

This uses the Green Agent (GPT-4o VLM) to evaluate progress on the current
incomplete milestone by analyzing the video clip.

Usage:
    python evaluate_with_progress.py \\
        --output_dir ./longterm_output/diamond_vpt \\
        --task_yaml task_configs/simple/mine_diamond_from_scratch.yaml

Date: 2026-01-14
"""

import sys
import os
import json
import argparse
from pathlib import Path

# Add parent directories to path
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

from utility.progress_evaluator import assess_progress_clip
from utility.read_conf import convert_yaml_to_callbacks


def evaluate_longterm_result(output_dir: Path, task_yaml: str):
    """
    Evaluate run_longterm_task.py results with continuous scoring.

    Args:
        output_dir: Output directory from run_longterm_task.py
        task_yaml: Path to task YAML configuration file

    Returns:
        dict: Evaluation results with continuous score
    """
    print(f"\n{'='*70}")
    print(f"CONTINUOUS SCORE EVALUATION")
    print(f"{'='*70}")
    print(f"Output directory: {output_dir}")
    print(f"Task config: {task_yaml}\n")

    # 1. Load milestone_tracking.json
    tracking_file = output_dir / 'milestone_tracking.json'
    if not tracking_file.exists():
        raise FileNotFoundError(f"Tracking file not found: {tracking_file}")

    with open(tracking_file, 'r') as f:
        tracking_data = json.load(f)

    # 2. Extract completed milestone count
    completed_count = tracking_data['milestones_achieved']
    total_milestones = tracking_data['total_milestones']
    task_name = tracking_data['task']

    print(f"Task: {task_name}")
    print(f"Completed milestones: {completed_count}/{total_milestones}")

    # 3. Evaluate current progress
    current_progress = 0.0
    progress_result = None

    if completed_count < total_milestones:
        # Check if video clip exists
        if 'current_progress_clip' not in tracking_data:
            print("\nWarning: No progress clip found. Progress = 0.0")
        else:
            clip_info = tracking_data['current_progress_clip']
            clip_path = Path(clip_info['video_path'])

            if not clip_path.exists():
                print(f"\nWarning: Progress clip not found: {clip_path}")
                print("Progress = 0.0")
            else:
                # Load task YAML to get criteria file
                if not os.path.exists(task_yaml):
                    raise FileNotFoundError(f"Task YAML not found: {task_yaml}")

                commands, task_dict, milestone_cfg = convert_yaml_to_callbacks(task_yaml)

                # Get current milestone config
                current_milestone_cfg = clip_info['milestone_cfg']
                milestone_identity = clip_info['milestone_target']

                # Determine criteria file path
                # Try to find it based on task name
                criteria_dir = Path(__file__).parent / 'auto_eval' / 'criteria_files'
                criteria_file = criteria_dir / f"{task_name}.txt"

                if not criteria_file.exists():
                    # Try with underscores replaced
                    criteria_file = criteria_dir / f"{task_name.replace(' ', '_')}.txt"

                if not criteria_file.exists():
                    print(f"\nWarning: Criteria file not found: {criteria_file}")
                    print("Using basic progress evaluation...")
                    criteria_file = None

                # Evaluate progress using Green Agent
                print(f"\n{'='*70}")
                print(f"Evaluating progress on: {milestone_identity}")
                print(f"Video clip: {clip_path}")
                print(f"{'='*70}")

                if criteria_file and criteria_file.exists():
                    progress_result = assess_progress_clip(
                        task_name=task_name,
                        milestone_identity=milestone_identity,
                        milestone_cfg=current_milestone_cfg,
                        video_path=str(clip_path),
                        criteria_file=str(criteria_file)
                    )
                    current_progress = progress_result['progress_0_1']
                else:
                    print("Skipping VLM evaluation (no criteria file)")
                    current_progress = 0.0
    else:
        print("\nAll milestones completed! Progress = 0.0 (task done)")

    # 4. Calculate final continuous score
    final_score = completed_count + current_progress

    # 5. Print results
    print(f"\n{'='*70}")
    print(f"FINAL RESULTS")
    print(f"{'='*70}")
    print(f"Task: {task_name}")
    print(f"Completed milestones: {completed_count}")
    print(f"Current milestone progress: {current_progress:.3f}")
    print(f"Total continuous score: {final_score:.3f} / {total_milestones}")
    print(f"Completion rate: {(final_score/total_milestones)*100:.2f}%")
    print(f"{'='*70}\n")

    # 6. Build result dict
    result = {
        'task': task_name,
        'completed_milestones': completed_count,
        'total_milestones': total_milestones,
        'current_progress': {
            'milestone_identity': tracking_data.get('current_progress_clip', {}).get('milestone_target'),
            'progress_score': current_progress,
            'evaluation': progress_result
        },
        'continuous_score': final_score,
        'completion_rate': (final_score / total_milestones) * 100,
        'original_tracking': tracking_data
    }

    # 7. Save results
    output_file = output_dir / 'continuous_evaluation.json'
    with open(output_file, 'w') as f:
        json.dump(result, f, indent=2)

    print(f"Results saved to: {output_file}\n")

    return result


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Evaluate long-term task results with continuous scoring',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Evaluate diamond task results
  python evaluate_with_progress.py \\
      --output_dir ./longterm_output/diamond_vpt \\
      --task_yaml task_configs/simple/mine_diamond_from_scratch.yaml

  # Evaluate dragon task results
  python evaluate_with_progress.py \\
      --output_dir ./longterm_output/dragon_steve1 \\
      --task_yaml task_configs/simple/kill_ender_dragon.yaml
        """
    )

    parser.add_argument(
        '--output_dir',
        type=str,
        required=True,
        help='Output directory from run_longterm_task.py'
    )
    parser.add_argument(
        '--task_yaml',
        type=str,
        required=True,
        help='Path to task YAML file (e.g., task_configs/simple/mine_diamond_from_scratch.yaml)'
    )

    args = parser.parse_args()

    try:
        evaluate_longterm_result(
            output_dir=Path(args.output_dir),
            task_yaml=args.task_yaml
        )
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
