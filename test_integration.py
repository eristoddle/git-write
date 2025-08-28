#!/usr/bin/env python3
"""
GitWrite Integration Test
Tests the complete API workflow to verify all components work together.
"""

import requests
import json
import sys
from pathlib import Path

API_BASE = "http://localhost:8000"
WEB_BASE = "http://localhost:5174"

def test_api_authentication():
    """Test API authentication"""
    print("🔐 Testing API Authentication...")
    
    # Test login
    response = requests.post(f"{API_BASE}/token", data={
        "username": "johndoe",
        "password": "secret"
    })
    
    if response.status_code != 200:
        print(f"❌ Authentication failed: {response.status_code}")
        print(response.text)
        return None
    
    token_data = response.json()
    token = token_data.get("access_token")
    
    if not token:
        print("❌ No access token in response")
        return None
    
    print(f"✅ Authentication successful, token length: {len(token)}")
    return token

def test_repository_listing(token):
    """Test repository listing API"""
    print("📁 Testing Repository Listing...")
    
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(f"{API_BASE}/repositorys", headers=headers)
    
    if response.status_code != 200:
        print(f"❌ Repository listing failed: {response.status_code}")
        print(response.text)
        return False
    
    repos_data = response.json()
    print(f"✅ Found {repos_data.get('count', 0)} repositories")
    
    if repos_data.get('count', 0) > 0:
        print(f"   Repository: {repos_data['repositories'][0]['name']}")
        return repos_data['repositories'][0]['name']
    
    return None

def test_repository_tree(token, repo_name):
    """Test repository tree browsing API"""
    print("🌳 Testing Repository Tree API...")
    
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(f"{API_BASE}/repository/{repo_name}/tree/master", headers=headers)
    
    if response.status_code != 200:
        print(f"❌ Repository tree failed: {response.status_code}")
        print(response.text)
        return False
    
    tree_data = response.json()
    entries = tree_data.get('entries', [])
    print(f"✅ Found {len(entries)} entries in repository root")
    
    for entry in entries[:3]:  # Show first 3 entries
        print(f"   {entry['type']}: {entry['name']} ({entry.get('size', 'N/A')} bytes)")
    
    return True

def test_repository_tree_subdirectory(token, repo_name):
    """Test repository tree browsing API for subdirectories"""
    print("📂 Testing Repository Tree API (subdirectory)...")
    
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(f"{API_BASE}/repository/{repo_name}/tree/master?path=src", headers=headers)
    
    if response.status_code != 200:
        print(f"❌ Repository tree subdirectory failed: {response.status_code}")
        print(response.text)
        return False
    
    tree_data = response.json()
    entries = tree_data.get('entries', [])
    breadcrumb = tree_data.get('breadcrumb', [])
    
    print(f"✅ Found {len(entries)} entries in src/ directory")
    print(f"   Breadcrumb: {' > '.join([b['name'] for b in breadcrumb])}")
    
    for entry in entries:
        print(f"   {entry['type']}: {entry['name']}")
    
    return True

def test_web_app_accessibility():
    """Test if web application is accessible"""
    print("🌐 Testing Web Application Accessibility...")
    
    try:
        response = requests.get(WEB_BASE, timeout=5)
        if response.status_code == 200 and "gitwrite" in response.text.lower():
            print("✅ Web application is accessible")
            return True
        else:
            print(f"❌ Web application returned {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Web application not accessible: {e}")
        return False

def test_other_api_endpoints(token):
    """Test other important API endpoints"""
    print("🔧 Testing Other API Endpoints...")
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # Test branches endpoint
    response = requests.get(f"{API_BASE}/repository/branches", headers=headers)
    if response.status_code == 200:
        branches = response.json().get('branches', [])
        print(f"✅ Branches API: Found {len(branches)} branches")
    else:
        print(f"⚠️ Branches API failed: {response.status_code}")
    
    # Test commits endpoint
    response = requests.get(f"{API_BASE}/repository/commits", headers=headers)
    if response.status_code == 200:
        commits = response.json().get('commits', [])
        print(f"✅ Commits API: Found {len(commits)} commits")
    else:
        print(f"⚠️ Commits API failed: {response.status_code}")
    
    return True

def main():
    """Run all integration tests"""
    print("🚀 GitWrite Integration Test Suite")
    print("=" * 50)
    
    # Test API authentication
    token = test_api_authentication()
    if not token:
        print("❌ Cannot proceed without authentication")
        sys.exit(1)
    
    # Test repository listing
    repo_name = test_repository_listing(token)
    if not repo_name:
        print("⚠️ No repositories found - creating test data might be needed")
    
    # Test repository tree (if we have a repo)
    if repo_name:
        test_repository_tree(token, repo_name)
        test_repository_tree_subdirectory(token, repo_name)
    
    # Test web application
    test_web_app_accessibility()
    
    # Test other endpoints
    test_other_api_endpoints(token)
    
    print("\n" + "=" * 50)
    print("🎉 Integration Test Complete!")
    print("\n📋 Next Steps:")
    print("1. Open browser to http://localhost:5174")
    print("2. Login with username: johndoe, password: secret")
    print("3. Verify repository listing and browsing works")
    print("4. Test file viewing and other features")

if __name__ == "__main__":
    main()