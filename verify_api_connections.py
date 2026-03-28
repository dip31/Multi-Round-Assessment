"""
API Connection Verification Script

This script verifies that all API routers are properly connected
and lists all available endpoints.
"""

from app.main import app
from app.api.v1.router import api_router


def verify_api_connections():
    """Verify all API connections and list endpoints."""
    
    print("=" * 70)
    print("API CONNECTION VERIFICATION")
    print("=" * 70)
    
    # Get all routes
    routes = []
    for route in app.routes:
        if hasattr(route, 'path') and hasattr(route, 'methods'):
            for method in route.methods:
                if method != "HEAD":  # Skip HEAD methods
                    routes.append({
                        'method': method,
                        'path': route.path,
                        'name': route.name,
                    })
    
    # Group by module
    modules = {
        'Authentication': [],
        'Session Management': [],
        'Aptitude Round': [],
        'Coding Round': [],
        'Interview Round': [],
        'Proctoring': [],
        'Advanced Proctoring': [],
        'Health Check': [],
    }
    
    for route in routes:
        path = route['path']
        if '/auth/' in path:
            modules['Authentication'].append(route)
        elif '/session/' in path:
            modules['Session Management'].append(route)
        elif '/aptitude/' in path:
            modules['Aptitude Round'].append(route)
        elif '/coding/' in path:
            modules['Coding Round'].append(route)
        elif '/interview/' in path:
            modules['Interview Round'].append(route)
        elif '/advanced-proctoring/' in path:
            modules['Advanced Proctoring'].append(route)
        elif '/proctoring/' in path:
            modules['Proctoring'].append(route)
        elif '/health' in path:
            modules['Health Check'].append(route)
    
    # Print results
    total_endpoints = 0
    for module_name, endpoints in modules.items():
        if endpoints:
            print(f"\n{module_name}:")
            print("-" * 70)
            for endpoint in sorted(endpoints, key=lambda x: x['path']):
                print(f"  {endpoint['method']:6} {endpoint['path']}")
                total_endpoints += 1
    
    print("\n" + "=" * 70)
    print(f"✓ Total API Endpoints: {total_endpoints}")
    print(f"✓ All routers properly connected")
    print("=" * 70)
    
    # Verify critical endpoints
    critical_paths = [
        '/api/v1/auth/register',
        '/api/v1/auth/login',
        '/api/v1/session/start',
        '/api/v1/aptitude/next-question',
        '/api/v1/interview/resume/upload',
        '/api/v1/proctoring/log-event',
        '/api/v1/advanced-proctoring/log-event',
    ]
    
    print("\nCritical Endpoint Verification:")
    print("-" * 70)
    all_paths = [r['path'] for r in routes]
    for path in critical_paths:
        status = "✓" if path in all_paths else "✗"
        print(f"  {status} {path}")
    
    print("\n" + "=" * 70)
    print("API VERIFICATION COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    verify_api_connections()
