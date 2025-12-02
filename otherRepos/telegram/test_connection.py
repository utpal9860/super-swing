"""
Test network connectivity for Telegram
"""
import socket
import sys


def test_port(host, port, timeout=5):
    """Test if a port is accessible"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        
        if result == 0:
            print(f"[OK] Port {port} on {host} is OPEN")
            return True
        else:
            print(f"[FAIL] Port {port} on {host} is CLOSED or FILTERED")
            return False
    except socket.gaierror:
        print(f"[ERROR] Could not resolve hostname: {host}")
        return False
    except Exception as e:
        print(f"[ERROR] {e}")
        return False


def test_telegram_connectivity():
    """Test connectivity to Telegram servers"""
    print("=" * 60)
    print("TESTING TELEGRAM CONNECTIVITY")
    print("=" * 60)
    
    # Telegram uses these ports
    telegram_servers = [
        ("149.154.167.50", 443, "DC 2"),
        ("149.154.175.53", 443, "DC 4"),
        ("91.108.56.181", 443, "DC 5"),  # Your DC
    ]
    
    results = []
    
    for host, port, dc_name in telegram_servers:
        print(f"\nTesting {dc_name} ({host}:{port})...")
        result = test_port(host, port, timeout=10)
        results.append(result)
    
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    success_count = sum(results)
    total_count = len(results)
    
    if success_count == total_count:
        print(f"[SUCCESS] All {total_count} Telegram servers are accessible!")
        print("   Your network/firewall is NOT blocking Telegram.")
    elif success_count > 0:
        print(f"[PARTIAL] {success_count}/{total_count} servers accessible")
        print("   Some connections work, try running the script again.")
    else:
        print(f"[FAIL] No Telegram servers accessible (0/{total_count})")
        print("\nPossible issues:")
        print("   1. Firewall is blocking port 443")
        print("   2. Corporate network restrictions")
        print("   3. ISP blocking Telegram")
        print("   4. VPN/Proxy interference")
        print("\nSolutions:")
        print("   - Disable firewall temporarily and test")
        print("   - Try from a different network (mobile hotspot)")
        print("   - Use a VPN if Telegram is blocked in your region")
    
    print("=" * 60)


if __name__ == "__main__":
    test_telegram_connectivity()

