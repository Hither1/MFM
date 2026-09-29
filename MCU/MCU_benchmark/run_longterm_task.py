"""
Long-term task evaluation script for MCU benchmark.
Supports: kill_ender_dragon, mine_diamond_from_scratch

This script runs long-term Minecraft tasks with comprehensive milestone tracking.
Outputs include MP4 video and JSON milestone data for evaluation.

Usage Examples:
    # Diamond task with VPT model (default)
    python run_longterm_task.py --task diamond --model vpt

    # Ender dragon with STEVE-1 model
    python run_longterm_task.py --task dragon --model steve1

    # Custom step count and output path
    python run_longterm_task.py --task diamond --steps 10000 --output ./my_results

    # Change video FPS
    python run_longterm_task.py --task dragon --fps 30

Date: 2026-01-11
"""

import argparse
import sys
import os
import time
import torch
from pathlib import Path

# Path setup - use environment variable or script location
MCU_PATH = os.getenv('MCU_PATH')
if MCU_PATH is None:
    # Default to parent directory of this script
    script_dir = Path(__file__).parent
    MCU_PATH = str(script_dir.parent)

benchmark_path = os.path.join(MCU_PATH, 'MCU_benchmark')
sys.path.insert(0, benchmark_path)
os.chdir(benchmark_path)


from minestudio.simulator import MinecraftSim
from minestudio.simulator.callbacks import (
    CommandsCallback,
    RecordCallback,
    FastResetCallback,
)
from minestudio.models.vpt import VPTPolicy
from minestudio.models.steve_one import SteveOnePolicy
from utility.read_conf import convert_yaml_to_callbacks
from utility.task_call import TaskCallback
from utility.milestone_tracker import MilestoneTrackerCallback


# Task configurations
TASK_CONFIGS = {
    'dragon': {
        'yaml': 'task_configs/simple/kill_ender_dragon.yaml',
        'name': 'kill_ender_dragon',
        'default_steps': 12000,  # 22 milestones, needs more time
    },
    'diamond': {
        'yaml': 'task_configs/simple/mine_diamond_from_scratch.yaml',
        'name': 'mine_diamond_from_scratch',
        'default_steps': 6000,  # 8 milestones
    }
}


def load_model(model_type):
    """
    Load VPT or STEVE-1 model.

    Args:
        model_type: 'vpt' or 'steve1'

    Returns:
        tuple: (model, model_name)
    """
    if model_type == 'vpt':
        print("\nLoading VPT model from Hugging Face...")
        try:
            # Try RL-trained model first (better for exploration)
            model = VPTPolicy.from_pretrained(
                "CraftJarvis/MineStudio_VPT.rl_from_early_game_2x"
            ).to("cuda")
            print("Loaded: VPT (rl_from_early_game_2x)")
        except Exception as e:
            print(f"Failed to load RL model: {e}")
            print("Trying fallback model...")
            # Fallback to foundation model
            model = VPTPolicy.from_pretrained(
                "CraftJarvis/MineStudio_VPT.foundation_2x"
            ).to("cuda")
            print("Loaded: VPT (foundation_2x)")
        return model, 'vpt'

    elif model_type == 'steve1':
        print("\nLoading STEVE-1 model from Hugging Face...")
        model = SteveOnePolicy.from_pretrained(
            "CraftJarvis/MineStudio_STEVE-1.official"
        ).to("cuda")
        print("Loaded: STEVE-1")
        return model, 'steve1'

    else:
        raise ValueError(f"Unknown model type: {model_type}. Choose 'vpt' or 'steve1'")


def run_task(task_name, model_type, num_steps, output_path, fps=20):
    """
    Run a long-term task with milestone tracking.

    Args:
        task_name: 'dragon' or 'diamond'
        model_type: 'vpt' or 'steve1'
        num_steps: Number of steps to run
        output_path: Directory to save outputs
        fps: Video FPS (default: 20)
    """

    # Load task configuration
    task_cfg = TASK_CONFIGS[task_name]
    yaml_path = task_cfg['yaml']

    print("=" * 70)
    print(f"Task: {task_cfg['name']}")
    print(f"Model: {model_type.upper()}")
    print(f"Steps: {num_steps}")
    print(f"Output: {output_path}")
    print("=" * 70)

    # Parse YAML config
    commands, task_dict, milestone_reward_cfg = convert_yaml_to_callbacks(yaml_path)
    print(f"\nLoaded {len(milestone_reward_cfg)} milestones from config")
    print(f"Task description: {task_dict.get('text', 'N/A')}")

    # Create output directory
    output_path = Path(output_path)
    output_path.mkdir(parents=True, exist_ok=True)

    # Setup callbacks
    callbacks = [
        TaskCallback(task_dict),
        MilestoneTrackerCallback(
            reward_cfg=milestone_reward_cfg,
            output_path=output_path,
            task_name=task_cfg['name']
        ),
        FastResetCallback(
            biomes=['plains', 'forest'],
            random_tp_range=1000,
        ),
        RecordCallback(
            record_path=str(output_path),
            fps=fps,
            frame_type='pov',
        ),
    ]

    # Add CommandsCallback if there are init commands
    if commands:
        callbacks.insert(0, CommandsCallback(commands))
        print(f"Loaded {len(commands)} initialization commands")

    # Create environment
    print("\nCreating Minecraft environment...")
    sim = MinecraftSim(obs_size=(128, 128), callbacks=callbacks)

    # Load model
    model, model_name = load_model(model_type)
    model.eval()

    # Run episode
    print(f"\nStarting episode...")
    print("-" * 70)

    obs, info = sim.reset()

    # Initialize model state
    if model_name == 'vpt':
        memory = None
    else:  # steve1
        condition = model.prepare_condition({
            'cond_scale': 4.0,
            'text': task_dict.get('text', task_cfg['name'])
        })
        state_in = model.initial_state(1, condition)

    total_reward = 0
    milestones_count = 0
    start_time = time.time()

    for step in range(num_steps):
        # Get action from model
        if model_name == 'vpt':
            action, memory = model.get_action(obs, memory, input_shape='*')
        else:  # steve1
            image = obs['image']
            if image.ndim == 3:
                image = image[None, None,...] 
            elif image.ndim == 4:
                image = image[None,...] 
            image = torch.tensor(image, dtype=torch.uint8, device='cuda')
            action, state_in = model.get_action(
                {
                    'image': image,
                    'condition': condition
                }, 
                state_in
            )

        # Step environment
        obs, reward, done, truncated, info = sim.step(action)
        if step == 0: 
            print("Observation and action:")
            print(f"  Observation: {obs}")
            print(f"  Action: {action}")

        # Track progress
        if reward > 0:
            total_reward += reward
            milestones_count += 1
            elapsed = time.time() - start_time
            print(f"[Step {step:5d}] Milestone achieved! "
                  f"(+{reward:.1f}) | Total: {total_reward:.1f} | "
                  f"Time: {elapsed:.1f}s")

        if done:
            print(f"\n[Step {step}] Episode ended (terminated)")
            break

        # Progress indicator every 1000 steps
        if step % 1000 == 0 and step > 0:
            elapsed = time.time() - start_time
            print(f"[Step {step:5d}] Progress check - "
                  f"Reward: {total_reward:.1f}, "
                  f"Milestones: {milestones_count}/{len(milestone_reward_cfg)}, "
                  f"Time: {elapsed:.1f}s")

    # Cleanup
    sim.close()

    # Summary
    elapsed = time.time() - start_time
    print("\n" + "=" * 70)
    print("RESULTS SUMMARY")
    print("=" * 70)
    print(f"Total steps: {step + 1}")
    print(f"Total time: {elapsed:.1f}s ({elapsed/60:.1f} minutes)")
    print(f"Total reward: {total_reward:.1f}")
    print(f"Milestones achieved: {milestones_count} / {len(milestone_reward_cfg)}")
    completion_pct = (milestones_count / len(milestone_reward_cfg)) * 100
    print(f"Completion rate: {completion_pct:.1f}%")
    print(f"\nOutputs saved to: {output_path}")
    print(f"  - Video: episode_0.mp4")
    print(f"  - Milestone data: milestone_tracking.json")
    print("=" * 70)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Run long-term Minecraft tasks with milestone tracking',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Diamond task with VPT
  python run_longterm_task.py --task diamond --model vpt

  # Ender dragon with STEVE-1
  python run_longterm_task.py --task dragon --model steve1 --steps 15000

  # Custom output path
  python run_longterm_task.py --task diamond --output ./results/exp1
        """
    )

    parser.add_argument(
        '--task',
        type=str,
        required=True,
        choices=['dragon', 'diamond'],
        help='Task to run: dragon (kill_ender_dragon) or diamond (mine_diamond_from_scratch)'
    )
    parser.add_argument(
        '--model',
        type=str,
        default='vpt',
        choices=['vpt', 'steve1'],
        help='Model to use: vpt or steve1 (default: vpt)'
    )
    parser.add_argument(
        '--steps',
        type=int,
        default=None,
        help='Number of steps to run (default: 6000 for diamond, 12000 for dragon)'
    )
    parser.add_argument(
        '--output',
        type=str,
        default=None,
        help='Output directory (default: ./longterm_output/{task}_{model})'
    )
    parser.add_argument(
        '--fps',
        type=int,
        default=20,
        help='Video FPS (default: 20)'
    )

    args = parser.parse_args()

    # Set defaults based on task
    task_cfg = TASK_CONFIGS[args.task]
    num_steps = args.steps if args.steps is not None else task_cfg['default_steps']
    output_path = args.output or f'./longterm_output/{args.task}_{args.model}'

    # Run the task
    try:
        run_task(
            task_name=args.task,
            model_type=args.model,
            num_steps=num_steps,
            output_path=output_path,
            fps=args.fps
        )
    except KeyboardInterrupt:
        print("\n\nInterrupted by user. Exiting...")
        sys.exit(0)
    except Exception as e:
        print(f"\n\nError occurred: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
