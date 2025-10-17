#!/usr/bin/env python3
"""
Network Configuration Helper for Agent Orchestrator
Helps configure network settings for server and worker communication.
"""

import json
import socket
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple


def get_local_ip() -> Optional[str]:
    """Get the local IP address of this machine."""
    try:
        # Connect to a remote address to determine local IP
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
        return local_ip
    except Exception:
        return None


def get_network_interfaces() -> List[Dict[str, str]]:
    """Get network interface information."""
    interfaces = []
    
    try:
        import psutil
        
        for interface, addrs in psutil.net_if_addrs().items():
            for addr in addrs:
                if addr.family == 2:  # AF_INET (IPv4)
                    interfaces.append({
                        "name": interface,
                        "ip": addr.address,
                        "netmask": addr.netmask,
                        "broadcast": addr.broadcast
                    })
                    break
    except ImportError:
        print("psutil not available. Install with: pip install psutil")
    
    return interfaces


def get_gateway() -> Optional[str]:
    """Get the default gateway."""
    try:
        if sys.platform == "win32":
            # Windows
            result = subprocess.run(
                ["route", "print", "0.0.0.0"],
                capture_output=True,
                text=True,
                check=True
            )
            lines = result.stdout.split('\n')
            for line in lines:
                if "0.0.0.0" in line and "0.0.0.0" in line:
                    parts = line.split()
                    if len(parts) >= 3:
                        return parts[2]
        else:
            # Linux/macOS
            result = subprocess.run(
                ["ip", "route", "show", "default"],
                capture_output=True,
                text=True,
                check=True
            )
            parts = result.stdout.split()
            if "via" in parts:
                idx = parts.index("via")
                if idx + 1 < len(parts):
                    return parts[idx + 1]
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    
    return None


def get_dns_servers() -> List[str]:
    """Get DNS server addresses."""
    dns_servers = []
    
    try:
        if sys.platform == "win32":
            # Windows
            result = subprocess.run(
                ["nslookup", "google.com"],
                capture_output=True,
                text=True,
                check=True
            )
            # Parse DNS servers from nslookup output
            lines = result.stdout.split('\n')
            for line in lines:
                if "Server:" in line:
                    parts = line.split()
                    if len(parts) >= 2:
                        dns_servers.append(parts[1])
        else:
            # Linux/macOS
            with open('/etc/resolv.conf', 'r') as f:
                for line in f:
                    if line.startswith('nameserver'):
                        dns_servers.append(line.split()[1])
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    
    return dns_servers


def detect_network_config() -> Dict[str, any]:
    """Detect current network configuration."""
    local_ip = get_local_ip()
    interfaces = get_network_interfaces()
    gateway = get_gateway()
    dns_servers = get_dns_servers()
    
    # Determine subnet
    subnet = None
    if local_ip and gateway:
        # Simple subnet detection (assumes /24)
        ip_parts = local_ip.split('.')
        if len(ip_parts) == 4:
            subnet = f"{ip_parts[0]}.{ip_parts[1]}.{ip_parts[2]}.0/24"
    
    return {
        "local_ip": local_ip,
        "gateway": gateway,
        "subnet": subnet,
        "dns_servers": dns_servers,
        "interfaces": interfaces
    }


def generate_server_config(network_config: Dict[str, any], machine_type: str = "workstation") -> str:
    """Generate server configuration based on network detection."""
    local_ip = network_config.get("local_ip")
    gateway = network_config.get("gateway")
    subnet = network_config.get("subnet")
    dns_servers = network_config.get("dns_servers", [])
    
    if machine_type == "workstation":
        # This is the worker
        worker_ip = local_ip
        # Assume server is on same subnet with .100
        if local_ip:
            ip_parts = local_ip.split('.')
            if len(ip_parts) == 4:
                server_ip = f"{ip_parts[0]}.{ip_parts[1]}.{ip_parts[2]}.100"
            else:
                server_ip = "192.168.1.100"
        else:
            server_ip = "192.168.1.100"
    else:
        # This is the server
        server_ip = local_ip
        # Assume worker is on same subnet with .101
        if local_ip:
            ip_parts = local_ip.split('.')
            if len(ip_parts) == 4:
                worker_ip = f"{ip_parts[0]}.{ip_parts[1]}.{ip_parts[2]}.101"
            else:
                worker_ip = "192.168.1.101"
        else:
            worker_ip = "192.168.1.101"
    
    config_lines = [
        "# Network Configuration",
        f"# Detected on: {socket.gethostname()}",
        f"# Local IP: {local_ip}",
        f"# Gateway: {gateway}",
        f"# Subnet: {subnet}",
        "",
        "# Server Configuration",
        f"SERVER_HOST=server.local",
        f"SERVER_INTERNAL_IP={server_ip}",
        "",
        "# Worker Configuration", 
        f"WORKER_HOST=worker.local",
        f"WORKER_INTERNAL_IP={worker_ip}",
        "",
        "# Network Configuration",
        f"LAN_SUBNET={subnet or '192.168.1.0/24'}",
        f"LAN_GATEWAY={gateway or '192.168.1.1'}",
        f"LAN_DNS={dns_servers[0] if dns_servers else '192.168.1.1'}",
        ""
    ]
    
    return "\n".join(config_lines)


def update_env_file(config_content: str, env_file: str = ".env") -> None:
    """Update environment file with network configuration."""
    env_path = Path(env_file)
    
    if env_path.exists():
        # Read existing content
        with open(env_path, 'r') as f:
            existing_content = f.read()
        
        # Remove old network config section
        lines = existing_content.split('\n')
        new_lines = []
        skip_section = False
        
        for line in lines:
            if line.startswith("# Network Configuration"):
                skip_section = True
                new_lines.append(config_content)
                continue
            elif skip_section and line.startswith("# ") and not line.startswith("# Network"):
                skip_section = False
                new_lines.append(line)
            elif not skip_section:
                new_lines.append(line)
        
        # Write updated content
        with open(env_path, 'w') as f:
            f.write('\n'.join(new_lines))
    else:
        # Create new file
        with open(env_path, 'w') as f:
            f.write(config_content)


def main():
    """Main function to configure network settings."""
    print("🌐 Detecting network configuration...")
    
    # Detect network configuration
    network_config = detect_network_config()
    
    # Print current network info
    print(f"  Local IP: {network_config.get('local_ip', 'Unknown')}")
    print(f"  Gateway: {network_config.get('gateway', 'Unknown')}")
    print(f"  Subnet: {network_config.get('subnet', 'Unknown')}")
    print(f"  DNS Servers: {', '.join(network_config.get('dns_servers', []))}")
    
    # Determine machine type
    machine_type = input("\nIs this machine the (s)erver or (w)orkstation? [w]: ").lower().strip()
    if machine_type not in ['s', 'server']:
        machine_type = "workstation"
    else:
        machine_type = "server"
    
    # Generate configuration
    config_content = generate_server_config(network_config, machine_type)
    
    # Update .env file
    update_env_file(config_content)
    
    print(f"\n✅ Network configuration updated in .env")
    print(f"📋 Machine type: {machine_type}")
    
    # Save network config for reference
    network_file = Path("network-config.json")
    with open(network_file, 'w') as f:
        json.dump(network_config, f, indent=2)
    
    print(f"💾 Network configuration saved to {network_file}")
    
    print(f"\n💡 Next steps:")
    print(f"  1. Review the network configuration in .env")
    print(f"  2. Update hostnames if needed (server.local, worker.local)")
    print(f"  3. Configure DNS or /etc/hosts for hostname resolution")
    print(f"  4. Test connectivity between server and worker")


if __name__ == "__main__":
    main()
