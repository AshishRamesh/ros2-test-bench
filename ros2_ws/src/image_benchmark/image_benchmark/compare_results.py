#!/usr/bin/env python3
"""
Compare Results Tool
Generates comparison graphs from multiple benchmark runs.
"""

import os
import sys
import json
import argparse
from glob import glob

import numpy as np
import pandas as pd

# Matplotlib with non-GUI backend for container
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def load_results(result_dirs):
    """Load results from multiple benchmark directories."""
    results = []

    for path in result_dirs:
        if os.path.isdir(path):
            summary_file = os.path.join(path, 'summary.json')
            if os.path.exists(summary_file):
                with open(summary_file, 'r') as f:
                    data = json.load(f)
                    data['_path'] = path
                    data['_name'] = os.path.basename(path)
                    results.append(data)
            else:
                print(f'Warning: No summary.json in {path}')
        else:
            print(f'Warning: {path} is not a directory')

    return results


def generate_comparison_plots(results, output_dir):
    """Generate comparison plots from multiple results."""
    if len(results) < 2:
        print('Need at least 2 results to compare')
        return

    plt.style.use('seaborn-v0_8-darkgrid')
    os.makedirs(output_dir, exist_ok=True)

    # Extract middleware names and colors
    colors = ['#2ecc71', '#3498db', '#e74c3c', '#9b59b6', '#f39c12']
    middlewares = [r['metadata']['middleware'] for r in results]

    # 1. Latency Comparison (Box Plot)
    fig, ax = plt.subplots(figsize=(12, 6))

    latency_data = []
    labels = []
    for r in results:
        raw_csv = os.path.join(r['_path'], 'raw_data.csv')
        if os.path.exists(raw_csv):
            df = pd.read_csv(raw_csv)
            latencies = df['latency_ms'].dropna()
            latencies = latencies[latencies >= 0]  # Filter negative
            if len(latencies) > 0:
                latency_data.append(latencies.values)
                labels.append(r['metadata']['middleware'].upper())

    if latency_data:
        bp = ax.boxplot(latency_data, labels=labels, patch_artist=True)
        for patch, color in zip(bp['boxes'], colors[:len(latency_data)]):
            patch.set_facecolor(color)
            patch.set_alpha(0.7)

        ax.set_ylabel('Latency (ms)')
        ax.set_title('Latency Comparison Across Middlewares')
        ax.grid(True, alpha=0.3)

        # Add median values as text
        for i, data in enumerate(latency_data):
            median = np.median(data)
            ax.annotate(f'{median:.1f}ms', xy=(i+1, median),
                       xytext=(5, 5), textcoords='offset points', fontsize=9)

    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'latency_comparison.png'), dpi=150)
    plt.close()
    print('Saved: latency_comparison.png')

    # 2. FPS Comparison (Bar Chart)
    fig, ax = plt.subplots(figsize=(12, 6))

    x = np.arange(len(results))
    width = 0.35

    sent_fps = []
    recv_fps = []
    for r in results:
        sent_fps.append(r.get('publisher_stats', {}).get('avg_fps_reported', 0))
        recv_fps.append(r.get('subscriber_stats', {}).get('avg_fps_received', 0))

    bars1 = ax.bar(x - width/2, sent_fps, width, label='Published FPS', color='#3498db', alpha=0.8)
    bars2 = ax.bar(x + width/2, recv_fps, width, label='Received FPS', color='#2ecc71', alpha=0.8)

    ax.set_xlabel('Middleware')
    ax.set_ylabel('Frames per Second')
    ax.set_title('FPS Comparison: Published vs Received')
    ax.set_xticks(x)
    ax.set_xticklabels([m.upper() for m in middlewares])
    ax.legend()
    ax.grid(True, alpha=0.3, axis='y')

    # Add value labels
    for bar in bars1:
        height = bar.get_height()
        if height > 0:
            ax.annotate(f'{height:.1f}', xy=(bar.get_x() + bar.get_width()/2, height),
                       xytext=(0, 3), textcoords='offset points', ha='center', fontsize=9)
    for bar in bars2:
        height = bar.get_height()
        if height > 0:
            ax.annotate(f'{height:.1f}', xy=(bar.get_x() + bar.get_width()/2, height),
                       xytext=(0, 3), textcoords='offset points', ha='center', fontsize=9)

    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'fps_comparison.png'), dpi=150)
    plt.close()
    print('Saved: fps_comparison.png')

    # 3. Frame Loss Comparison (Bar Chart)
    fig, ax = plt.subplots(figsize=(10, 6))

    frame_loss = [r.get('subscriber_stats', {}).get('frame_loss_percent', 0) for r in results]

    bars = ax.bar(range(len(results)), frame_loss, color=colors[:len(results)], alpha=0.8)
    ax.set_xlabel('Middleware')
    ax.set_ylabel('Frame Loss (%)')
    ax.set_title('Frame Loss Comparison')
    ax.set_xticks(range(len(results)))
    ax.set_xticklabels([m.upper() for m in middlewares])
    ax.grid(True, alpha=0.3, axis='y')

    # Add value labels
    for bar, loss in zip(bars, frame_loss):
        ax.annotate(f'{loss:.2f}%', xy=(bar.get_x() + bar.get_width()/2, bar.get_height()),
                   xytext=(0, 3), textcoords='offset points', ha='center', fontsize=10)

    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'frame_loss_comparison.png'), dpi=150)
    plt.close()
    print('Saved: frame_loss_comparison.png')

    # 4. Jitter Comparison (Box Plot)
    fig, ax = plt.subplots(figsize=(12, 6))

    jitter_data = []
    labels = []
    for r in results:
        raw_csv = os.path.join(r['_path'], 'raw_data.csv')
        if os.path.exists(raw_csv):
            df = pd.read_csv(raw_csv)
            inter_frame = df['inter_frame_ms'].dropna()
            inter_frame = inter_frame[inter_frame > 0]
            if len(inter_frame) > 0:
                jitter_data.append(inter_frame.values)
                labels.append(r['metadata']['middleware'].upper())

    if jitter_data:
        bp = ax.boxplot(jitter_data, labels=labels, patch_artist=True)
        for patch, color in zip(bp['boxes'], colors[:len(jitter_data)]):
            patch.set_facecolor(color)
            patch.set_alpha(0.7)

        ax.set_ylabel('Inter-frame Time (ms)')
        ax.set_title('Jitter Comparison (Inter-frame Time Variation)')
        ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'jitter_comparison.png'), dpi=150)
    plt.close()
    print('Saved: jitter_comparison.png')

    # 5. Summary Table
    fig, ax = plt.subplots(figsize=(14, 6))
    ax.axis('off')

    # Prepare table data
    columns = ['Middleware', 'Recv FPS', 'Frame Loss %', 'Latency (ms)', 'Jitter Std (ms)', 'Bandwidth (MB/s)']
    table_data = []

    for r in results:
        row = [
            r['metadata']['middleware'].upper(),
            f"{r.get('subscriber_stats', {}).get('avg_fps_received', 0):.1f}",
            f"{r.get('subscriber_stats', {}).get('frame_loss_percent', 0):.2f}%",
            f"{r.get('latency_ms', {}).get('mean', 0):.1f} (p95: {r.get('latency_ms', {}).get('p95', 0):.1f})",
            f"{r.get('jitter_ms', {}).get('std', 0):.2f}",
            f"{r.get('bandwidth', {}).get('avg_mbps', 0):.2f}"
        ]
        table_data.append(row)

    table = ax.table(cellText=table_data, colLabels=columns, loc='center', cellLoc='center')
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.scale(1.2, 1.8)

    # Style header
    for i in range(len(columns)):
        table[(0, i)].set_facecolor('#3498db')
        table[(0, i)].set_text_props(color='white', fontweight='bold')

    # Alternate row colors
    for i in range(1, len(table_data) + 1):
        for j in range(len(columns)):
            if i % 2 == 0:
                table[(i, j)].set_facecolor('#ecf0f1')

    ax.set_title('Benchmark Summary Comparison', fontsize=14, fontweight='bold', pad=20)

    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'summary_table.png'), dpi=150, bbox_inches='tight')
    plt.close()
    print('Saved: summary_table.png')

    # Save comparison JSON
    comparison = {
        'middlewares': middlewares,
        'comparison': []
    }

    for r in results:
        comparison['comparison'].append({
            'middleware': r['metadata']['middleware'],
            'timestamp': r['metadata']['timestamp'],
            'fps_received': r.get('subscriber_stats', {}).get('avg_fps_received', 0),
            'frame_loss_percent': r.get('subscriber_stats', {}).get('frame_loss_percent', 0),
            'latency_mean_ms': r.get('latency_ms', {}).get('mean', 0),
            'latency_p95_ms': r.get('latency_ms', {}).get('p95', 0),
            'jitter_std_ms': r.get('jitter_ms', {}).get('std', 0),
            'bandwidth_mbps': r.get('bandwidth', {}).get('avg_mbps', 0)
        })

    with open(os.path.join(output_dir, 'comparison.json'), 'w') as f:
        json.dump(comparison, f, indent=2)
    print('Saved: comparison.json')


def main(args=None):
    parser = argparse.ArgumentParser(description='Compare benchmark results from multiple middlewares')
    parser.add_argument('result_dirs', nargs='+', help='Paths to result directories')
    parser.add_argument('-o', '--output', default='/ros2_ws/results/comparison',
                       help='Output directory for comparison plots')

    # Handle ROS 2 args format
    if args is None:
        args = sys.argv[1:]

    # Filter out ROS 2 specific arguments
    filtered_args = []
    skip_next = False
    for i, arg in enumerate(args):
        if skip_next:
            skip_next = False
            continue
        if arg == '--ros-args':
            break
        filtered_args.append(arg)

    parsed = parser.parse_args(filtered_args)

    # Expand glob patterns
    result_dirs = []
    for pattern in parsed.result_dirs:
        expanded = glob(pattern)
        if expanded:
            result_dirs.extend(expanded)
        else:
            result_dirs.append(pattern)

    print(f'Loading results from {len(result_dirs)} directories...')
    results = load_results(result_dirs)

    if not results:
        print('Error: No valid results found')
        sys.exit(1)

    print(f'Found {len(results)} valid results:')
    for r in results:
        print(f'  - {r["metadata"]["middleware"]}: {r["_name"]}')

    print(f'\nGenerating comparison plots in {parsed.output}...')
    generate_comparison_plots(results, parsed.output)

    print(f'\nComparison complete! Results saved to: {parsed.output}')


if __name__ == '__main__':
    main()
