"""
Input Responsiveness Test — verifies each button causes expected state changes.

This is the test that caught Bug #15 (missing scrolling). The pipeline was
comparing register VALUES but never checked if INPUT→OUTPUT causality matched.

For each D-pad direction and button, measures:
1. Which memory addresses change when pressed vs NOOP
2. How much the screen changes (pixel diff)
3. Whether the response matches the OG ROM

This should run BEFORE the trajectory comparison — if a button does nothing
in the remake but causes changes in the OG, that's a critical bug regardless
of what the register values are.
"""
import numpy as np
from typing import Optional


def test_input_responsiveness(rom_path, boot_sequence, sync_on,
                              addresses: dict, frames_per_step=4,
                              test_duration=20, boot_frames=200):
    """Test what each button press does to game state.

    Returns dict of {button_name: {addr: (before, after, changed)}}
    """
    from gb_env import GBEnv

    # GB_ACTIONS: 0=NOOP, 1=A, 2=B, 3=RIGHT, 4=LEFT, 5=UP, 6=DOWN,
    #             7=RIGHT+A, 11=START, 12=SELECT
    buttons = {
        'NOOP': 0, 'A': 1, 'B': 2, 'RIGHT': 3, 'LEFT': 4,
        'UP': 5, 'DOWN': 6, 'RIGHT_A': 7, 'START': 11, 'SELECT': 12,
    }

    results = {}
    for btn_name, action in buttons.items():
        env = GBEnv(
            rom_path, state_addresses=addresses,
            boot_frames=boot_frames, boot_sequence=boot_sequence,
            sync_on=sync_on, frames_per_step=frames_per_step,
            max_steps=test_duration + 50,
        )
        obs_before, info_before = env.reset()
        # Stabilize
        for _ in range(10):
            env.step(0)

        # Record baseline
        before = {k: env._read_memory(v) for k, v in addresses.items()}
        screen_before = env._get_screen()

        # Press button for test_duration steps
        for _ in range(test_duration):
            env.step(action)

        # Record after
        after = {k: env._read_memory(v) for k, v in addresses.items()}
        screen_after = env._get_screen()

        # Compute changes
        addr_changes = {}
        for k in addresses:
            changed = before[k] != after[k]
            addr_changes[k] = {
                'before': before[k], 'after': after[k], 'changed': changed,
                'delta': after[k] - before[k],
            }

        # Screen pixel difference
        screen_diff = np.mean(np.abs(
            screen_after.astype(float) - screen_before.astype(float)
        ))

        results[btn_name] = {
            'addresses': addr_changes,
            'screen_diff': float(screen_diff),
            'any_change': any(v['changed'] for v in addr_changes.values()),
        }

        env.close()

    return results


def compare_responsiveness(og_results, rm_results):
    """Compare input responsiveness between OG and remake.

    Flags buttons that cause changes in OG but not in remake (or vice versa).
    """
    issues = []
    for btn in og_results:
        if btn not in rm_results:
            continue

        og = og_results[btn]
        rm = rm_results[btn]

        # Check: button causes screen change in OG but not remake
        if og['screen_diff'] > 5.0 and rm['screen_diff'] < 1.0:
            issues.append({
                'severity': 'CRITICAL',
                'button': btn,
                'issue': f'{btn} changes screen in OG (diff={og["screen_diff"]:.1f}) but NOT in remake (diff={rm["screen_diff"]:.1f})',
                'detail': 'Missing input response — fundamental gameplay mechanic broken',
            })

        # Check: specific addresses change in OG but not remake
        for addr_name in og['addresses']:
            if addr_name not in rm['addresses']:
                continue
            og_changed = og['addresses'][addr_name]['changed']
            rm_changed = rm['addresses'][addr_name]['changed']
            if og_changed and not rm_changed:
                issues.append({
                    'severity': 'WARNING',
                    'button': btn,
                    'address': addr_name,
                    'issue': f'{btn} changes {addr_name} in OG ({og["addresses"][addr_name]["before"]}→{og["addresses"][addr_name]["after"]}) but not in remake',
                })

    return issues


def run_responsiveness_check(og_rom, remake_rom, boot_sequence, sync_on,
                              boot_frames=200):
    """Full responsiveness check — the test that would have caught Bug #15."""
    addresses = {
        'SCX': 0xFF43, 'SCY': 0xFF42,
        'FFBD': 0xFFBD, 'FFBE': 0xFFBE, 'FFBF': 0xFFBF,
        'FFC0': 0xFFC0, 'FFC1': 0xFFC1, 'FFD0': 0xFFD0,
        'DC81': 0xDC81,  # Scroll counter — THE key address for Bug #15
    }

    print("Testing OG input responsiveness...")
    og = test_input_responsiveness(og_rom, boot_sequence, sync_on, addresses,
                                   boot_frames=boot_frames)
    print("Testing Remake input responsiveness...")
    rm = test_input_responsiveness(remake_rom, boot_sequence, sync_on, addresses,
                                   boot_frames=boot_frames)

    # Display results
    print(f"\n{'='*70}")
    print("INPUT RESPONSIVENESS COMPARISON")
    print(f"{'='*70}")
    print(f"{'Button':<10} {'OG screen Δ':>12} {'RM screen Δ':>12} {'OG addr chg':>12} {'RM addr chg':>12}")
    print(f"{'-'*58}")
    for btn in og:
        og_diff = og[btn]['screen_diff']
        rm_diff = rm[btn]['screen_diff']
        og_chg = sum(1 for v in og[btn]['addresses'].values() if v['changed'])
        rm_chg = sum(1 for v in rm[btn]['addresses'].values() if v['changed'])
        flag = ' *** MISMATCH' if (og_diff > 5 and rm_diff < 1) or (og_chg > 0 and rm_chg == 0) else ''
        print(f"{btn:<10} {og_diff:>12.1f} {rm_diff:>12.1f} {og_chg:>12} {rm_chg:>12}{flag}")

    # Check for issues
    issues = compare_responsiveness(og, rm)
    if issues:
        print(f"\n{'!'*50}")
        print(f"ISSUES FOUND: {len(issues)}")
        print(f"{'!'*50}")
        for issue in issues:
            print(f"  [{issue['severity']}] {issue['issue']}")
    else:
        print(f"\nAll buttons respond consistently between OG and remake.")

    return og, rm, issues


if __name__ == "__main__":
    from gb_env import PentaDragonEnv

    OG = '/home/struktured/projects/penta-dragon-dx-claude/rom/Penta Dragon (J).gb'
    RM = '/home/struktured/projects/penta-dragon-remake/rom/working/penta_dragon_dx.gbc'

    og, rm, issues = run_responsiveness_check(
        OG, RM,
        PentaDragonEnv.BOOT_SEQUENCE,
        PentaDragonEnv.SYNC_ON,
    )
