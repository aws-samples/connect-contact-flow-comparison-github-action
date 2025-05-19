from unittest.mock import Mock, patch

import pytest

from src.get_flows import main


@pytest.fixture
def mock_args():
    return Mock(
        token='test-token',
        owner='test-owner',
        repo='test-repo',
        commit='test-sha',
        contact_flow_path='contact-flows',
        output_dir='test-output',
        use_bedrock=True
    )

@pytest.mark.parametrize("use_bedrock", [True, False])
@patch('src.get_flows.get_aws_clients')
@patch('src.get_flows.get_file_paths')
@patch('src.get_flows.get_file_versions')
@patch('src.get_flows.save_versions')
@patch('src.get_flows.compare_contact_flows')
@patch('argparse.ArgumentParser.parse_args')
def test_main_success(
    mock_parse_args,
    mock_compare_flows,
    mock_save_versions,
    mock_get_versions,
    mock_get_paths,
    mock_get_aws_clients,
    mock_args,
    use_bedrock
):
    # Update mock_args with use_bedrock value
    mock_args.use_bedrock = use_bedrock
    # Mock AWS clients only if using Bedrock
    if use_bedrock:
        mock_get_aws_clients.return_value = (Mock(), "123456789012")
    mock_parse_args.return_value = mock_args
    mock_get_paths.return_value = ['contact-flows/flow1.json']
    mock_get_versions.return_value = ('{"test": "original"}', '{"test": "modified"}')
    # Set up metadata based on whether Bedrock is used
    if use_bedrock:
        mock_metadata = {
            'RequestId': 'test-request-id',
            'HTTPStatusCode': 200,
            'HTTPHeaders': {
                'x-amzn-bedrock-invocation-latency': '100',
                'x-amzn-bedrock-input-token-count': '50',
                'x-amzn-bedrock-output-token-count': '100',
                'date': '2024-01-01'
            },
            'RetryAttempts': 0
        }
    else:
        mock_metadata = {'ResponseMetadata': {'RequestId': 'N/A'}}
    mock_compare_flows.return_value = (['test.html'], mock_metadata)
    
    with patch('os.path.exists', return_value=False), \
         patch('os.makedirs') as mock_makedirs:
        main()
        
        mock_makedirs.assert_called_once()
        mock_get_paths.assert_called_once()
        mock_get_versions.assert_called_once()
        mock_save_versions.assert_called_once()
        mock_compare_flows.assert_called_once_with(
            'flow1',
            'flow1_original.json',
            'flow1_modified.json',
            use_bedrock
        )

@patch('argparse.ArgumentParser.parse_args')
def test_main_file_retrieval_error(mock_parse_args, mock_args):
    mock_parse_args.return_value = mock_args
    
    with patch('src.get_flows.get_file_paths', side_effect=Exception("API Error")):
        with pytest.raises(Exception) as exc_info:
            main()
        assert str(exc_info.value) == "API Error"
