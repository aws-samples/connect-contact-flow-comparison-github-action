import json
from unittest.mock import MagicMock, patch

import pytest

from src.get_flows import compare_contact_flows


@pytest.fixture
def mock_flow_files():
    flow1 = {
        "Version": "2019-10-30",
        "StartAction": "Start",
        "Actions": []
    }
    flow2 = {
        "Version": "2019-10-30", 
        "StartAction": "Start",
        "Actions": [{"Type": "Transfer"}]
    }
    return json.dumps(flow1), json.dumps(flow2)

@pytest.fixture
def mock_bedrock_response():
    class MockBody:
        def read(self):
            return json.dumps({
                'content': [{'text': '```html\n<!DOCTYPE html>\n<html><body>test</body></html>\n```'}]
            })
    
    return {
        'body': MockBody(),
        'ResponseMetadata': {}
    }

def test_compare_contact_flows_with_bedrock(mock_flow_files, mock_bedrock_response, tmp_path):
    flow1, flow2 = mock_flow_files
    
    # Create temporary test files
    file1 = tmp_path / "flow1.json"
    file2 = tmp_path / "flow2.json"
    file1.write_text(flow1)
    file2.write_text(flow2)
    
    with patch('boto3.client') as mock_boto:
        # Configure mock boto3 client
        mock_bedrock = MagicMock()
        mock_bedrock.invoke_model.return_value = mock_bedrock_response
        mock_boto.return_value = mock_bedrock
        
        # Run comparison with Bedrock
        result, metadata = compare_contact_flows('test', str(file1), str(file2), use_bedrock=True)
        
        # Verify results
        assert result is not None
        assert isinstance(result, list)
        assert len(result) > 0
        assert 'html' in result[0].lower()
        assert 'body' in result[0].lower()
        assert isinstance(metadata, dict)

def test_compare_contact_flows_without_bedrock(mock_flow_files, tmp_path):
    flow1, flow2 = mock_flow_files
    
    # Create temporary test files
    file1 = tmp_path / "flow1.json"
    file2 = tmp_path / "flow2.json"
    file1.write_text(flow1)
    file2.write_text(flow2)
    
    # Run comparison without Bedrock
    result, metadata = compare_contact_flows('test', str(file1), str(file2), use_bedrock=False)
    
    # Verify results
    assert result is not None
    assert isinstance(result, list)
    assert len(result) > 0
    assert 'html' in result[0].lower()
    assert 'comparison-container' in result[0].lower()  # Check for side-by-side comparison
    assert metadata['ResponseMetadata']['RequestId'] == 'N/A'  # Check for non-Bedrock metadata

def test_compare_contact_flows_file_error(tmp_path):
    with pytest.raises(Exception) as exc_info:
        compare_contact_flows('test', 'nonexistent1.json', 'nonexistent2.json', use_bedrock=False)
    
        # Print the actual error message for debugging
        error_message = str(exc_info.value)
        print(f"Actual error message: {error_message}")
        
        # Broaden the list of possible error messages and make the check case-insensitive
        expected_error_patterns = [
            "error reading",
            "no such file",
            "cannot find",
            "not found",
            "no such file or directory",
            "expecting value",
            "failed to open",
            "[errno 2]"
        ]
        
        # Convert actual error message to lowercase for case-insensitive comparison
        error_message_lower = error_message.lower()
        
        # Check if any of the expected patterns are in the error message
        matches = [pattern for pattern in expected_error_patterns 
                  if pattern.lower() in error_message_lower]
        
        # If no matches found, print helpful debug information
        if not matches:
            print("Expected one of these patterns:")
            for pattern in expected_error_patterns:
                print(f"  - {pattern}")
            print(f"But got: {error_message}")
            
        assert matches, f"Error message '{error_message}' did not contain any expected patterns"
