#!/usr/bin/env python3
"""
Analyze Minecraft ender_dragon_half runs: milestones, phase costs, and bottlenecks.
"""
import re
import sys
from collections import defaultdict
from pathlib import Path

# Milestone order (as given in the task)
MILESTONE_ORDER = [
    'mine_log', 'crafting_table', 'wooden_pickaxe', 'mine_cobblestone', 
    'stone_pickaxe', 'mine_iron_ore', 'furnace', 'iron_ingot', 'iron_pickaxe', 
    'mine_diamond_ore',  # These 10 are given
    'diamond', 'diamond_pickaxe', 'diamond_sword', 'mine_obsidian', 
    'flint_and_steel', 'netherrack', 'kill_blaze', 'blaze_rod', 
    'kill_enderman', 'ender_pearl', 'blaze_powder', 'eye_of_ender', 
    'end_stone', 'kill_ender_dragon'
]

RUNS = {
    'og6': '/datapool/data3/storage/ruihan/data_share/jh/Collab/MFM-grid-merge-mcu/output/og6_mfm/episode_001/memory/logs.txt',
    'og7': '/datapool/data3/storage/ruihan/data_share/jh/Collab/MFM-grid-merge-mcu/output/og7_mfm/episode_001/memory/logs.txt',
    'og8': '/datapool/data3/storage/ruihan/data_share/jh/Collab/MFM-grid-merge-mcu/output/og8_mfm/episode_001/memory/logs.txt',
    'og9': '/datapool/data3/storage/ruihan/data_share/jh/Collab/MFM-grid-merge-mcu/output/og9_mfm/episode_001/memory/logs.txt',
    'og10': '/datapool/data3/storage/ruihan/data_share/jh/Collab/MFM-grid/MCU/output/og10_mfm/episode_001/memory/logs.txt',
    'og11': '/datapool/data3/storage/ruihan/data_share/jh/Collab/MFM-grid/MCU/output/og11_mfm/episode_001/memory/logs.txt',
    'og12': '/datapool/data3/storage/ruihan/data_share/jh/Collab/MFM-grid/MCU/output/og12_mfm/episode_001/memory/logs.txt',
    'og13': '/datapool/data3/storage/ruihan/data_share/jh/Collab/MFM-grid/MCU/output/og13_mfm/episode_001/memory/logs.txt',
    'og14': '/datapool/data3/storage/ruihan/data_share/jh/Collab/MFM-grid/MCU/output/og14_mfm/episode_001/memory/logs.txt',
}

def parse_log(log_path):
    """Parse log and return milestones, deaths, max_step."""
    milestones = {}
    deaths = []
    action_step_map = {}
    current_step = 0
    
    if not Path(log_path).exists():
        return {'milestones': {}, 'deaths': [], 'max_step': 0}
    
    with open(log_path, 'r', errors='replace') as f:
        for line in f:
            m = re.match(r'Action (\d+) \| Step (\d+)', line)
            if m:
                action_num = int(m.group(1))
                current_step = int(m.group(2))
                action_step_map[action_num] = current_step
            
            m = re.search(r'\[EVENT\] MILESTONE (\w+) verified', line)
            if m:
                milestone_name = m.group(1)
                if milestone_name not in milestones:
                    milestones[milestone_name] = current_step
            
            m = re.search(r'\[NOTE\] YOU DIED at \((.*?)\)', line)
            if m:
                coords = m.group(1)
                deaths.append((current_step, coords))
    
    max_step = max(action_step_map.values()) if action_step_map else 0
    
    return {
        'milestones': milestones,
        'deaths': deaths,
        'max_step': max_step
    }

def extract_phase_content(log_path, start_step, end_step):
    """Extract [PLAN] and [NOTE] content from a phase."""
    current_step = 0
    plans = []
    note_counts = defaultdict(int)
    note_samples = []
    
    if not Path(log_path).exists():
        return [], {}, []
    
    with open(log_path, 'r', errors='replace') as f:
        for line in f:
            m = re.match(r'Action \d+ \| Step (\d+)', line)
            if m:
                current_step = int(m.group(1))
            
            if start_step <= current_step <= end_step:
                if '[PLAN]' in line:
                    plans.append((current_step, line.strip()))
                
                if '[NOTE]' in line:
                    note_samples.append((current_step, line.strip()))
                    # Count note types
                    if 'YOU DIED' in line:
                        note_counts['YOU_DIED'] += 1
                    elif 'governor' in line:
                        note_counts['governor'] += 1
                    elif 'LAVA' in line:
                        note_counts['LAVA_AHEAD'] += 1
                    else:
                        m = re.search(r'\[NOTE\] ([a-zA-Z_]+)', line)
                        if m:
                            note_type = m.group(1)
                            note_counts[note_type] += 1
    
    # Sample plans approximately every 1000 steps
    sample_plans = []
    if plans:
        step_range = end_step - start_step
        if step_range > 0:
            targets = set()
            for i in range(5):
                targets.add(start_step + int((i + 1) * step_range / 5))
            for step, plan in plans:
                if step in targets and len(sample_plans) < 5:
                    sample_plans.append(plan)
    
    return sample_plans, dict(note_counts), note_samples

def get_phase_milestones_for_run(run_data):
    """
    Identify key phases:
    - start -> diamond_sword (kit phase)
    - diamond_sword -> mine_obsidian
    - mine_obsidian + flint_and_steel held -> netherrack (portal built)
    - Rebuild costs after deaths
    """
    milestones = run_data['milestones']
    deaths = run_data['deaths']
    ordered_ms = sorted(milestones.items(), key=lambda x: x[1])
    
    phases = []
    
    # Phase 1: start -> diamond_sword (kit phase)
    if 'diamond_sword' in milestones:
        sword_step = milestones['diamond_sword']
        phases.append({
            'name': 'kit_phase',
            'desc': 'start -> diamond_sword',
            'start_step': 0,
            'end_step': sword_step,
            'cost': sword_step,
        })
    
    # Phase 2: diamond_sword -> mine_obsidian
    if 'diamond_sword' in milestones and 'mine_obsidian' in milestones:
        sword_step = milestones['diamond_sword']
        obsidian_step = milestones['mine_obsidian']
        phases.append({
            'name': 'sword_to_obsidian',
            'desc': 'diamond_sword -> mine_obsidian',
            'start_step': sword_step,
            'end_step': obsidian_step,
            'cost': obsidian_step - sword_step,
        })
    
    # Phase 3: obsidian -> portal (flint_and_steel or netherrack)
    obsidian_step = milestones.get('mine_obsidian', None)
    flint_step = milestones.get('flint_and_steel', None)
    nether_step = milestones.get('netherrack', None)
    
    if obsidian_step and (flint_step or nether_step):
        portal_step = min([s for s in [flint_step, nether_step] if s is not None])
        phases.append({
            'name': 'obsidian_to_portal',
            'desc': 'mine_obsidian -> portal (flint_and_steel/netherrack)',
            'start_step': obsidian_step,
            'end_step': portal_step,
            'cost': portal_step - obsidian_step,
        })
    
    # Phase 4: Death rebuild costs
    death_rebuild_phases = []
    for death_step, coords in deaths:
        # Find next milestone after death
        next_ms = [s for n, s in ordered_ms if s > death_step]
        if next_ms:
            next_step = next_ms[0]
            next_name = [n for n, s in ordered_ms if s == next_step][0]
            death_rebuild_phases.append({
                'name': f'death_rebuild_{len(death_rebuild_phases)}',
                'desc': f'death at step {death_step} -> {next_name}',
                'start_step': death_step,
                'end_step': next_step,
                'cost': next_step - death_step,
            })
    
    phases.extend(death_rebuild_phases)
    
    return phases

if __name__ == '__main__':
    # Load all runs
    all_runs = {}
    for run_name, log_path in RUNS.items():
        all_runs[run_name] = parse_log(log_path)
    
    # Print summary table
    print("=" * 80)
    print("RUN DATA SUMMARY")
    print("=" * 80)
    for run_name in sorted(all_runs.keys()):
        data = all_runs[run_name]
        ms = data['milestones']
        deaths = data['deaths']
        print(f"\n{run_name}:")
        print(f"  Final step: {data['max_step']}")
        print(f"  Milestones verified: {len(ms)}")
        print(f"  Deaths: {len(deaths)}")
        if ms:
            print(f"  Milestone steps (by order achieved):")
            for name, step in sorted(ms.items(), key=lambda x: x[1])[:5]:
                print(f"    {name}: {step}")
            print(f"    ...")
        if deaths:
            for step, coords in deaths:
                print(f"  Death at step {step}")
    
    # Analyze phases for each run
    print("\n" + "=" * 80)
    print("PHASE ANALYSIS")
    print("=" * 80)
    for run_name in sorted(all_runs.keys()):
        data = all_runs[run_name]
        phases = get_phase_milestones_for_run(data)
        if phases:
            print(f"\n{run_name}:")
            for phase in phases:
                print(f"  {phase['desc']}: {phase['cost']} steps")

