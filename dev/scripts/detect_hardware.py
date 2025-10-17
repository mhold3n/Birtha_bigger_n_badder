#!/usr/bin/env python3
"""
Hardware Detection Script for Agent Orchestrator
Detects current machine's hardware specifications and generates configuration.
"""

import json
import platform
import subprocess
import sys
from pathlib import Path
from typing import Dict, Any, Optional


def get_gpu_info() -> Dict[str, Any]:
    """Detect GPU information using nvidia-smi."""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            check=True
        )
        
        lines = result.stdout.strip().split('\n')
        gpus = []
        
        for line in lines:
            if line.strip():
                parts = line.split(', ')
                if len(parts) >= 3:
                    gpus.append({
                        "name": parts[0].strip(),
                        "memory_mb": int(parts[1].strip()),
                        "driver_version": parts[2].strip()
                    })
        
        return {"gpus": gpus, "count": len(gpus)}
    except (subprocess.CalledProcessError, FileNotFoundError):
        return {"gpus": [], "count": 0, "error": "nvidia-smi not found or failed"}


def get_cpu_info() -> Dict[str, Any]:
    """Get CPU information."""
    try:
        cpu_count = platform.processor()
        logical_cores = platform.processor_count()
        
        # Try to get physical cores on Linux
        physical_cores = logical_cores
        try:
            with open('/proc/cpuinfo', 'r') as f:
                content = f.read()
                physical_cores = content.count('processor')
        except FileNotFoundError:
            pass
        
        return {
            "processor": cpu_count,
            "logical_cores": logical_cores,
            "physical_cores": physical_cores
        }
    except Exception as e:
        return {"error": str(e)}


def get_memory_info() -> Dict[str, Any]:
    """Get memory information."""
    try:
        if platform.system() == "Linux":
            with open('/proc/meminfo', 'r') as f:
                meminfo = f.read()
            
            for line in meminfo.split('\n'):
                if line.startswith('MemTotal:'):
                    mem_kb = int(line.split()[1])
                    mem_gb = mem_kb / 1024 / 1024
                    return {"total_gb": round(mem_gb, 1)}
        
        # Fallback for other systems
        import psutil
        mem = psutil.virtual_memory()
        return {"total_gb": round(mem.total / 1024**3, 1)}
    except Exception as e:
        return {"error": str(e)}


def get_network_info() -> Dict[str, Any]:
    """Get network interface information."""
    try:
        import psutil
        
        interfaces = {}
        for interface, addrs in psutil.net_if_addrs().items():
            for addr in addrs:
                if addr.family == 2:  # AF_INET
                    interfaces[interface] = {
                        "ip": addr.address,
                        "netmask": addr.netmask
                    }
                    break
        
        return {"interfaces": interfaces}
    except Exception as e:
        return {"error": str(e)}


def get_disk_info() -> Dict[str, Any]:
    """Get disk information."""
    try:
        import psutil
        
        disk_usage = psutil.disk_usage('/')
        return {
            "total_gb": round(disk_usage.total / 1024**3, 1),
            "free_gb": round(disk_usage.free / 1024**3, 1),
            "used_gb": round(disk_usage.used / 1024**3, 1)
        }
    except Exception as e:
        return {"error": str(e)}


def detect_machine_type() -> str:
    """Detect if this is likely a server or workstation based on hardware."""
    gpu_info = get_gpu_info()
    
    if gpu_info.get("count", 0) > 0:
        return "workstation"
    else:
        return "server"


def generate_env_config(hardware_info: Dict[str, Any]) -> str:
    """Generate environment configuration based on hardware detection."""
    machine_type = detect_machine_type()
    
    config_lines = [
        "# Generated hardware configuration",
        f"# Machine type: {machine_type}",
        f"# Detected on: {platform.node()}",
        ""
    ]
    
    if machine_type == "workstation":
        gpu_info = hardware_info.get("gpu", {})
        if gpu_info.get("count", 0) > 0:
            gpu = gpu_info["gpus"][0]
            config_lines.extend([
                "# GPU Configuration",
                f"GPU_MODEL={gpu['name'].replace(' ', '_').upper()}",
                f"GPU_MEMORY_GB={gpu['memory_mb'] // 1024}",
                f"GPU_DRIVER_VERSION={gpu['driver_version']}",
                ""
            ])
    
    cpu_info = hardware_info.get("cpu", {})
    if "logical_cores" in cpu_info:
        config_lines.extend([
            "# CPU Configuration",
            f"CPU_CORES={cpu_info['logical_cores']}",
            ""
        ])
    
    memory_info = hardware_info.get("memory", {})
    if "total_gb" in memory_info:
        config_lines.extend([
            "# Memory Configuration",
            f"RAM_GB={memory_info['total_gb']}",
            ""
        ])
    
    return "\n".join(config_lines)


def main():
    """Main function to detect hardware and generate configuration."""
    print("🔍 Detecting hardware configuration...")
    
    hardware_info = {
        "machine_type": detect_machine_type(),
        "hostname": platform.node(),
        "platform": platform.platform(),
        "cpu": get_cpu_info(),
        "memory": get_memory_info(),
        "gpu": get_gpu_info(),
        "network": get_network_info(),
        "disk": get_disk_info()
    }
    
    # Save hardware inventory
    inventory_file = Path("machine-inventory.json")
    with open(inventory_file, 'w') as f:
        json.dump(hardware_info, f, indent=2)
    
    print(f"✅ Hardware inventory saved to {inventory_file}")
    
    # Generate environment configuration
    env_config = generate_env_config(hardware_info)
    
    # Save to machine-specific env file
    machine_type = hardware_info["machine_type"]
    env_file = Path(f".env.{machine_type}")
    
    with open(env_file, 'w') as f:
        f.write(env_config)
    
    print(f"✅ Environment configuration saved to {env_file}")
    
    # Print summary
    print("\n📊 Hardware Summary:")
    print(f"  Machine Type: {hardware_info['machine_type']}")
    print(f"  Hostname: {hardware_info['hostname']}")
    print(f"  Platform: {hardware_info['platform']}")
    
    if "cpu" in hardware_info:
        cpu = hardware_info["cpu"]
        print(f"  CPU: {cpu.get('logical_cores', 'Unknown')} cores")
    
    if "memory" in hardware_info:
        memory = hardware_info["memory"]
        print(f"  Memory: {memory.get('total_gb', 'Unknown')} GB")
    
    if "gpu" in hardware_info:
        gpu = hardware_info["gpu"]
        print(f"  GPU: {gpu.get('count', 0)} detected")
        for i, gpu_info in enumerate(gpu.get("gpus", [])):
            print(f"    GPU {i+1}: {gpu_info['name']} ({gpu_info['memory_mb']} MB)")
    
    print(f"\n💡 Next steps:")
    print(f"  1. Review and update {env_file}")
    print(f"  2. Update network configuration with actual IP addresses")
    print(f"  3. Configure server settings when Proxmox is online")


if __name__ == "__main__":
    main()
