"""
Contact Flow Comparison Tool

This script compares Amazon Connect contact flow configurations between different versions in a GitHub repository
using Amazon Bedrock for intelligent comparison and visualization.

Dependencies:
- boto3
- ghapi
- mermaid.js (loaded via CDN in generated HTML)

Required AWS Permissions:
- bedrock:InvokeModel
- bedrock-runtime:InvokeModel
- sts:GetCallerIdentity

Required Environment:
- AWS credentials configured
- GitHub Personal Access Token with repo access
"""

import argparse
import base64
import json
import logging
import os
import sys
from pathlib import Path

from ghapi.all import GhApi

from bedrock_utils import BedrockMetricsCollector, TokenRateLimiter, get_aws_clients, invoke_bedrock_with_retries

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def extract_code_simple(response):
    """
    Extracts code blocks from a text response containing markdown-style code blocks.
    
    Args:
        response (str): Text containing markdown code blocks delimited by ```
        
    Returns:
        list: List of extracted code block contents
    """
    try:
        # Split by code block markers and get content between them
        code_blocks = response.split('```')[1::2]
        # Remove language identifier if present
        return [block.split('\n', 1)[1] if '\n' in block else block 
                for block in code_blocks]
    except IndexError:
        logger.warning("No code blocks found in response")
        return []
       
def compare_contact_flows(fileName: str, file1_path: str, file2_path: str, use_bedrock: bool = True) -> tuple[list, dict]:
    """
    Compares two contact flow JSON files and generates an HTML visualization.
    If use_bedrock is True, uses Bedrock for intelligent comparison with Mermaid diagrams.
    If use_bedrock is False, creates a simple side-by-side JSON comparison.
    
    Args:
        fileName (str): Base name for output files
        file1_path (str): Path to original contact flow JSON
        file2_path (str): Path to modified contact flow JSON
        use_bedrock (bool): Whether to use Bedrock for comparison
        
    Returns:
        tuple: (list of generated HTML content, response metadata)
        
    Raises:
        Exception: If file reading fails
    """
    
    # Read and load the JSON files
    try:
        with open(file1_path, 'r') as f1, open(file2_path, 'r') as f2:
            flow1 = json.load(f1)
            flow2 = json.load(f2)
    except Exception as e:
        raise Exception(f"Error reading input files: {str(e)}") from e

    if not use_bedrock:
        # Create simple side-by-side comparison
        html_content = f"""<!DOCTYPE html>
        <html>
        <head>
            <title>Contact Flow Comparison - {fileName}</title>
            <style>
                body {{
                    margin: 40px;
                    font-family: Arial, sans-serif;
                    background-color: #f5f5f5;
                }}
                h1 {{
                    color: #333;
                    margin-bottom: 30px;
                }}
                .comparison-container {{
                    display: flex;
                    gap: 20px;
                    margin-top: 20px;
                }}
                .flow-version {{
                    flex: 1;
                    background: white;
                    padding: 20px;
                    border-radius: 8px;
                    box-shadow: 0 0 10px rgba(0,0,0,0.1);
                }}
                pre {{
                    white-space: pre-wrap;
                    word-wrap: break-word;
                    overflow-x: auto;
                }}
            </style>
        </head>
        <body>
            <h1>Contact Flow Comparison - {fileName}</h1>
            <div class="comparison-container">
                <div class="flow-version">
                    <h2>Original Version</h2>
                    <pre>{json.dumps(flow1, indent=2)}</pre>
                </div>
                <div class="flow-version">
                    <h2>Modified Version</h2>
                    <pre>{json.dumps(flow2, indent=2)}</pre>
                </div>
            </div>
        </body>
        </html>"""
        
        output_path = Path(f'{fileName}.html')
        output_path.write_text(html_content)
        return [html_content], {'ResponseMetadata': {'RequestId': 'N/A'}}

    # If use_bedrock is True, proceed with Bedrock comparison
    htmlTemplate = '''  <!DOCTYPE html>
<html>
<head>
    <title>ACME Contact Flow Comparison</title>
    <script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
    <style>
        body {
            margin: 40px;
            font-family: Arial, sans-serif;
            background-color: #f5f5f5;
        }
        h1 {
            color: #333;
            margin-bottom: 30px;
        }
        .flow-container {
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 0 10px rgba(0,0,0,0.1);
        }
    </style>
</head>
<body>
    <h1>ACME Contact Flow Comparison</h1>
    <div class="flow-container">
        <div class="mermaid">
        flowchart TD
            subgraph Flow1[Original Flow]
                A1[Start] --> B1[Update Flow Logging]
                B1 --> C1[Update Flow Attributes]
                C1 --> D1[Update Voice]
                D1 --> E1[Play Welcome Message]
                E1 --> F1[Update Contact Event Hooks]
                F1 --> G1[Connect with Lex Bot]
                G1 --> H1{Department Choice}
                H1 -->|Sales| I1[Set Sales Queue]
                H1 -->|Finance| J1[Set Finance Queue]
                I1 & J1 --> K1[Invoke Flow Module]
                K1 --> L1[Invoke Lambda]:::removed
                L1 --> M1[Transfer to Flow]
                M1 --> N1[Play Error Message]
                N1 --> O1[Disconnect]
            end

            Flow1 ~~~ Summary

            subgraph Flow2[Modified Flow]
                A2[Start] --> B2[Update Flow Logging]
                B2 --> C2[Update Flow Attributes]
                C2 --> D2[Update Voice]
                D2 --> E2[Play Welcome Message]
                E2 --> F2[Update Contact Event Hooks]
                F2 --> G2[Connect with Lex Bot]
                G2 --> H2{Department Choice}
                H2 -->|Sales| I2[Set Sales Queue]
                H2 -->|Finance| J2[Set Finance Queue]
                I2 & J2 --> K2[Invoke Flow Module]
                K2 --> L2[Play Welcome Message]:::added
                L2 --> M2[Transfer to Flow]
                M2 --> N2[Play Error Message]
                N2 --> O2[Disconnect]
            end

            Flow2 ~~~ Summary

            subgraph Summary[Changes Summary]
                S1[Removed Lambda Function Call]:::removed
                S2[Added Additional Welcome Message]:::added
                S3[Queue ARNs changed from dynamic to static]
                S4[Flow Module name explicitly specified]
            end

            classDef removed fill:#ff6b6b,stroke:#333,color:white
            classDef added fill:#4CAF50,stroke:#333,color:white
        </div>
    </div>

    <div style="margin-top: 30px; padding: 20px; background: white; border-radius: 8px;">
        <h2>Detailed Changes:</h2>
        <ul>
            <li>Removed Lambda function invocation (acme-exampleFunction)</li>
            <li>Added new Welcome Message block before Transfer to Flow</li>
            <li>Queue ARNs changed from dynamic (FlowAttributes.sales/finance) to static ARNs</li>
            <li>Flow Module name explicitly set to "VMX3-CoreFlowModule-tfdemo-dev-use1-amzconnect"</li>
            <li>Flow attributes structure remained same but implementation changed</li>
            <li>Error handling paths remained consistent</li>
            <li>Lex Bot integration parameters unchanged</li>
            <li>Contact Event Hooks configuration maintained</li>
        </ul>
    </div>

    <script>
        mermaid.initialize({
            theme: 'default',
            securityLevel: 'loose',
            startOnLoad: true,
            flowchart: {
                useMaxWidth: true,
                htmlLabels: true,
                curve: 'basis'
            }
        });
    </script>
</body>
</html>'''
    # Prepare the prompt
    prompt = f"""
    Compare these two contact flows and:
    Flow 1: {json.dumps(flow1, indent=2)}
    Flow 2: {json.dumps(flow2, indent=2)}
    
    <htmlTemplate>
    {htmlTemplate}
    </htmlTemplate>
    
    - create a visual representation of the differences between the first and second contact flows using Mermaid flow charts. 
    - Include detailed summary at bottom of what changed and embed summary into diagram. 
    - when using the blocks for invoke module, invoke lambda, or tranfer to flow make sure to call out the module name, lambda function name, or flow respectively. 
    - Make sure to highlight the items that have changed between the two flows by making the actions that were removed from first flow red and actions added to second flow green. If an action merely changed, make it orange.
    - IMPORTANT: Create a detailed summary of all items that changed between the two flows, including arns, parameters, etc., and embed at bottom of diagram. No change is too small. 
    - If the first flow is empty, assume that this is a brand new contact flow.
    - Embed the mermaid image into an html web page. 
    - Use the html within the <htmlTemplate> tags as a guide for how it should be configured. The only differences from the template should be the actual mermaid diagrams and summary.
    - ALWAYS provide the complete HTML in markdown code blocks delimited by ```. Do not ask if you should provide anything.
    """

    # Prepare the request for Bedrock
    request = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 4096,
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0,
        "top_p": 0.99
    }

    try:
      
        #Initialize AWS Clients
        bedrock_runtime, account_id = get_aws_clients()
        # Initialize utilities
        rate_limiter = TokenRateLimiter(tokens_per_minute=400000)
        response = invoke_bedrock_with_retries(bedrock_runtime, account_id, request, rate_limiter=rate_limiter)
        
        # Parse the response
        response_body = json.loads(response['body'].read())
        resp_metadata = response['ResponseMetadata']
        
        bedrock_response = response_body['content'][0]['text']
        logger.info("Model response:")
        logger.info(bedrock_response)
        logger.info("Response Metadata:")
        logger.info(resp_metadata)

        generated_html = extract_code_simple(bedrock_response)
        if not generated_html:
            raise Exception("No HTML content generated from Bedrock response")
        
        
        output_path = Path(f'{fileName}.html')
        output_path.write_text(generated_html[0])
        
        return generated_html, resp_metadata
                
    except Exception as e:
        logger.error(f"Error invoking Bedrock: {str(e)}")
        raise #Exception(f"Error invoking Bedrock: {str(e)}") from e
        
        

def get_file_paths(
    token: str,
    owner: str,
    repo: str,
    commit_sha: str,
    contact_flow_path: str
) -> list[str]:
    """
    Retrieves paths of modified contact flow files from a specific GitHub commit.
    
    Args:
        token (str): GitHub personal access token
        owner (str): Repository owner
        repo (str): Repository name
        commit_sha (str): Commit hash
        contact_flow_path (str): Base path for contact flow files
        
    Returns:
        list: List of modified file paths
    """
    # Initialize GitHub API client
    api = GhApi(token=token)
    
    # Get commit details
    commit = api.repos.get_commit(owner=owner, repo=repo, ref=commit_sha)
    
    filePaths = []
    for file in commit.files:
        if file.filename.startswith(contact_flow_path):
            if file.status in ('added', 'modified'):
                logger.info(f"File: {file.filename}, Status: {file.status}")
                filePaths.append(file.filename)
    
    return filePaths

def get_file_versions(
    token: str,
    owner: str,
    repo: str,
    commit_sha: str,
    file_path: str
) -> tuple[str | None, str | None]:
    """
    Retrieves original and modified versions of a file from GitHub.
    
    Args:
        token (str): GitHub personal access token
        owner (str): Repository owner
        repo (str): Repository name
        commit_sha (str): Commit hash
        file_path (str): Path to the file
        
    Returns:
        tuple: (original_content, modified_content) or (None, None) if retrieval fails
    """
    # Initialize GitHub API client
    api = GhApi(token=token)
    
    # Get commit details
    commit = api.repos.get_commit(owner=owner, repo=repo, ref=commit_sha)
    
    # Get parent commit SHA
    parent_sha = commit.parents[0].sha if commit.parents else None
    
    try:
        # Get original content (from parent commit)
        try:
            original_response = api.repos.get_content(
                owner=owner,
                repo=repo,
                path=file_path,
                ref=parent_sha
            )
            
            original_content = base64.b64decode(original_response.content).decode('utf-8')
            logger.info(f"original_content: {original_content}")
        except Exception as e:
            if hasattr(e, 'status') and e.status == 404:  # File doesn't exist in parent commit (new file)
                original_content = "{}"
            else:
                raise
        
        # Get modified content
        modified_response = api.repos.get_content(
            owner=owner,
            repo=repo,
            path=file_path,
            ref=commit_sha
        )
        modified_content = base64.b64decode(modified_response.content).decode('utf-8')
        
        logger.debug("original_content: ", original_content)
        logger.debug("modified_content: ", modified_content)
        return original_content, modified_content
    
    except Exception as e:
        logger.error(f"Error: {e}")
        return None, None

def save_versions(
    original: str,
    modified: str,
    original_path: str,
    modified_path: str
) -> None:
    try:
        with open(original_path, 'w') as f:
            f.write(original)
        with open(modified_path, 'w') as f:
            f.write(modified)
        logger.info(f"Files saved successfully:\n- Original: {original_path}\n- Modified: {modified_path}")
    except Exception as e:
        logger.error(f"Error saving files: {e}")
        raise


def main():
    # Set up argument parser
    parser = argparse.ArgumentParser(description='Download original and modified versions of a file from a GitHub commit')
    
    parser.add_argument('--token', '-t',
                        required=True,
                        help='GitHub personal access token')
    
    parser.add_argument('--owner', '-o',
                        required=True,
                        help='Repository owner')
    
    parser.add_argument('--repo', '-r',
                        required=True,
                        help='Repository name')
    
    parser.add_argument('--commit', '-c',
                        required=True,
                        help='Commit SHA')
    
    parser.add_argument('--contact_flow_path', '-p',
                        required=True,
                        help='Relative path for the directory containing contact flows')
    
    parser.add_argument('--output-dir', '-d',
                        default='.',
                        help='Output directory for saved files (default: current directory)')
    
    parser.add_argument('--use-bedrock', '-b',
                        type=lambda x: x.lower() == 'true',
                        default=True,
                        help='Whether to use Bedrock for comparison (default: true)')

    # Parse arguments
    args = parser.parse_args()

    # Create output directory if it doesn't exist
    if not os.path.exists(args.output_dir):
        os.makedirs(args.output_dir)

    # Get file versions
    logger.info(f"From commit: {args.commit}")
    
    # Initialize Metrics Collection if using Bedrock
    metrics_collector = BedrockMetricsCollector() if args.use_bedrock else None
    
    filepaths  = get_file_paths(
        args.token,
        args.owner,
        args.repo,
        args.commit,
        args.contact_flow_path
    )
    logger.info(f"Filepaths: {filepaths}")
    html_results = []
    for file in filepaths:
      logger.info(f"Retrieving file: {file}")
      original, modified = get_file_versions(
          args.token,
          args.owner,
          args.repo,
          args.commit,
          file
      )
    
      if original is None or modified is None:
        logger.error("Failed to retrieve file versions")
        sys.exit(1)
    
      fileName = file.split("/")[-1]
      logger.info(f"Filename: {fileName}")

      # Generate output file paths
      base_filename = os.path.basename(fileName.split(".")[0])
      file_extension = fileName.split(".")[-1]
      original_path = ".".join([f"{base_filename}_original", file_extension])
      modified_path = ".".join([f"{base_filename}_modified", file_extension])
      
      logger.debug(base_filename, original_path, modified_path)

      # Save files
      save_versions(original, modified, original_path, modified_path)
      
      html_result, resp_metadata = compare_contact_flows(base_filename, original_path, modified_path, args.use_bedrock)
      
      if html_result:
        html_results.append(f"{base_filename}.html")
      # Collect metrics if using Bedrock
      if metrics_collector:
          metrics_collector.add_metric(resp_metadata)
        
      logger.info(f"Comparison complete! Results saved to {base_filename}.html")
    
    # Process Bedrock Metrics if using Bedrock
    if metrics_collector:
        metrics_collector.save_metrics()
        metrics_collector.generate_html_report() 
    # Create index.html after processing all files
    logger.info(f"html_results: {html_results}")
    if html_results:
        with open('index.html', 'w') as f:
            f.write('''
            <html>
            <head>
                <title>Contact Flow Comparison</title>
                <style>
                    body { font-family: Arial, sans-serif; margin: 20px; }
                    h1 { color: #333; }
                    .link-list { margin: 20px 0; }
                    a { color: #0066cc; text-decoration: none; display: block; margin: 10px 0; }
                    a:hover { text-decoration: underline; }
                </style>
            </head>
            <body>
            ''')
            f.write(f'  <h1>Contact Flow Comparison Results for Commit {args.commit}</h1>')
            f.write('  <div class="link-list">')
            for result in html_results:
                f.write(f'      <a href="./{result}">{result}</a>\n')
            if args.use_bedrock:
                f.write('<a href="./bedrock_metrics.html">View API Metrics Report</a>')
            f.write('''
                </div>
            </body>
            </html>
            ''')
    logger.info("Index.html has been created with links to all comparison results.")
      

if __name__ == "__main__":
    main()
