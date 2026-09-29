'''
Milestone tracking callback for long-term tasks.
Extends RewardsCallback to save milestone achievement data to JSON.

Date: 2026-01-11
Updated: 2026-01-14 - Added video clipping for progress evaluation
'''

import time
import json
import cv2
import numpy as np
from pathlib import Path
from minestudio.simulator.callbacks import RewardsCallback


class MilestoneTrackerCallback(RewardsCallback):
    """
    Enhanced RewardsCallback that tracks milestone achievements with timestamps.

    Tracks:
    - Milestone achievement timestamps
    - Step numbers when achieved
    - Reward values
    - Cumulative progress

    Saves milestone data to JSON for easy evaluation and analysis.

    Args:
        reward_cfg: List of milestone reward configurations (same as RewardsCallback)
        output_path: Path to save milestone_tracking.json
        task_name: Name of the task (for JSON output)

    Example:
        callback = MilestoneTrackerCallback(
            reward_cfg=milestone_reward_cfg,
            output_path=Path('./output'),
            task_name='kill_ender_dragon'
        )
    """

    def __init__(self, reward_cfg, output_path, task_name='unknown'):
        super().__init__(reward_cfg)
        self.output_path = Path(output_path)
        self.task_name = task_name
        self.milestone_log = []  # List of achievement events
        self.start_time = None

    def after_reset(self, sim, obs, info):
        """Initialize tracking on episode reset."""
        self.start_time = time.time()
        self.milestone_log = []
        return super().after_reset(sim, obs, info)

    def after_step(self, sim, obs, reward, terminated, truncated, info):
        """Track milestone achievements during episode."""
        # Call parent to get reward and milestone updates
        obs, override_reward, terminated, truncated, info = super().after_step(
            sim, obs, reward, terminated, truncated, info
        )

        # Track new milestone achievements
        if override_reward > 0:
            # Check which milestones were newly achieved
            for cfg in self.reward_cfg:
                identity = cfg['identity']
                # If this milestone is now in memory but not yet logged
                if self.reward_memory.get(identity, 0) > 0 and \
                   identity not in [m['identity'] for m in self.milestone_log]:
                    self.milestone_log.append({
                        'identity': identity,
                        'step': self.current_step,
                        'timestamp': time.time() - self.start_time,
                        'reward': cfg['reward']
                    })

        return obs, override_reward, terminated, truncated, info

    def before_close(self, sim):
        """Save milestone data to JSON before closing."""
        self._save_milestone_json()

    def _clip_video_segment(self, video_path, start_step, end_step, output_path):
        """
        Extract a video segment from start_step to end_step.

        Args:
            video_path: Path to source video
            start_step: Starting step (frame number)
            end_step: Ending step (frame number)
            output_path: Path to save clipped video

        Returns:
            str: Path to clipped video, or None if clipping failed
        """
        try:
            cap = cv2.VideoCapture(str(video_path))
            if not cap.isOpened():
                print(f"Failed to open video: {video_path}")
                return None

            # Get video properties
            fps = int(cap.get(cv2.CAP_PROP_FPS))
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

            # Create video writer
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            out = cv2.VideoWriter(str(output_path), fourcc, fps, (width, height))

            # Set starting position
            cap.set(cv2.CAP_PROP_POS_FRAMES, start_step)

            # Read and write frames
            frame_count = 0
            frames_to_write = end_step - start_step

            while frame_count < frames_to_write:
                ret, frame = cap.read()
                if not ret:
                    break
                out.write(frame)
                frame_count += 1

            cap.release()
            out.release()

            print(f"Video clip saved: {output_path} ({frame_count} frames)")
            return str(output_path)

        except Exception as e:
            print(f"Error clipping video: {e}")
            return None

    def _save_milestone_json(self):
        """Save milestone tracking data to JSON file."""
        # Calculate summary statistics
        total_reward = sum(m['reward'] for m in self.milestone_log)
        milestones_achieved = len(self.milestone_log)
        total_milestones = len(self.reward_cfg)
        completion_rate = milestones_achieved / total_milestones if total_milestones > 0 else 0.0

        # Build milestone summary (all milestones with achievement status)
        milestone_summary = {}
        for cfg in self.reward_cfg:
            identity = cfg['identity']
            # Find if this milestone was achieved
            achieved_milestone = next(
                (m for m in self.milestone_log if m['identity'] == identity),
                None
            )

            if achieved_milestone:
                milestone_summary[identity] = {
                    'achieved': True,
                    'step': achieved_milestone['step'],
                    'timestamp': achieved_milestone['timestamp']
                }
            else:
                milestone_summary[identity] = {
                    'achieved': False,
                    'step': None,
                    'timestamp': None
                }

        # Construct output JSON
        output = {
            'task': self.task_name,
            'total_steps': self.current_step,
            'total_reward': total_reward,
            'milestones_achieved': milestones_achieved,
            'total_milestones': total_milestones,
            'completion_rate': completion_rate,
            'milestones': self.milestone_log,  # Sequential log
            'milestone_summary': milestone_summary  # Summary view
        }

        # Clip video for current progress evaluation (if incomplete)
        if milestones_achieved < total_milestones:
            # Find last completed milestone step
            last_completed_step = 0
            current_milestone_cfg = None

            if self.milestone_log:
                last_completed_step = self.milestone_log[-1]['step']

            # Find next incomplete milestone
            completed_identities = [m['identity'] for m in self.milestone_log]
            for cfg in self.reward_cfg:
                if cfg['identity'] not in completed_identities:
                    current_milestone_cfg = cfg
                    break

            # Create video clip if we have a current milestone
            if current_milestone_cfg:
                video_path = self.output_path / 'episode_0.mp4'
                clip_path = self.output_path / 'current_progress_clip.mp4'

                if video_path.exists():
                    clipped = self._clip_video_segment(
                        video_path=video_path,
                        start_step=last_completed_step,
                        end_step=self.current_step,
                        output_path=clip_path
                    )

                    if clipped:
                        output['current_progress_clip'] = {
                            'video_path': str(clip_path),
                            'milestone_target': current_milestone_cfg['identity'],
                            'milestone_cfg': current_milestone_cfg,
                            'start_step': last_completed_step,
                            'end_step': self.current_step
                        }

        # Save to file
        output_file = self.output_path / 'milestone_tracking.json'
        with open(output_file, 'w') as f:
            json.dump(output, f, indent=2)

        print(f"Milestone data saved to: {output_file}")
