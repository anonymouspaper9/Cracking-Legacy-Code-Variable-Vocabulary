# Custom
import api_endpoints
from args import args


# General Libraries
import os
import re
import time
import json

from openai import OpenAI



class Inference:
    def __init__(self, args):
        self.args = args
    
    def llm_provider_1_inference(self, prompt, model_name, return_raw=False):

        ## llm_provider_1 Configuration
        api_dict = api_endpoints.active_models_llm_provider_1.get(model_name)
        endpoint = api_dict['api_endpoint']
        model_id = api_dict['model_id']

        
        payload = {
            "model_id": model_id,
            "input": [{"role": "user", "content": prompt}],
            "parameters": {
                "temperature": self.args.temperature,
                "max_tokens": self.args.max_tokens,
                "top_p": self.args.top_p,
            }
        }
        
    
        try:
            client = OpenAI(
                api_key=self.args.llm_provider_1_API_KEY,
                base_url=f'{endpoint}/v1',
                default_headers={'llm_provider_1_API_KEY': self.args.llm_provider_1_API_KEY}
            )
    
            completions = client.chat.completions.create(
                model=payload["model_id"],
                messages=payload["input"], #[{"role": "user", "content": prompt}],
                **payload["parameters"]
            )
    
            raw_output = completions.to_dict()
            response = raw_output['choices'][0]['message']['content']
            
            if return_raw:
                return response, raw_output

            else:
                return response
            
        except Exception as e:
            print(f"llm_provider_1 API Exception : {e}")

            if return_raw:
                return e, e

            else:
                return e
            
        


    
    def litellm_inference(self, prompt, model_name, return_raw=False):
        """
        Perform inference using LiteLLM API compatible models (Claude versions).
        """
        # Get LiteLLM configuration details (api key, base url, etc.)
        api_dict = api_endpoints.active_models_litellm.get(model_name)
        if not api_dict:
            raise ValueError(f"Missing api_key or {api_dict['base_url_env']}.")

        base_url = api_dict["base_url_env"]
        model_id = api_dict["model_id"]
        api_key = self.args.litellm_api_key


        if not api_key or not base_url:
            raise ValueError(f"Missing {'api_key_env'} or {api_dict['base_url_env']}")

        # Initialize client
        client = OpenAI(api_key=api_key, base_url=base_url)

        retries = 5


        for attempt in range(retries):
            try:
                raw_output = client.chat.completions.create(
                    model=model_id,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=self.args.max_tokens,
                    extra_body = {
                        "thinking": {"type": "disabled"}
                    },
                    temperature=self.args.temperature,
                    timeout=60,
                )

                content = raw_output.choices[0].message.content.strip()

                
                    

                if not content:
                    print(f"[Retry {attempt+1}/{retries}] Empty response from LiteLLM. Retrying...")
                    
                if return_raw:
                    return content, raw_output 
    
                else:
                    return content


                
                    
                
                

            except Exception as e:
                print(f"[Retry {attempt+1}/{retries}] LiteLLM Exception: {e}")

            # exponential backoff before retry
            if attempt < retries - 1:
                time.sleep(2 ** attempt)

        print(f"[FAILED] All {retries} LiteLLM attempts failed. Returning fallback.")
        return None

    
    def __call__(self, prompt, inference_platform, model_name, return_raw=False):

    
        if inference_platform =="llm_provider_1":
            return self.llm_provider_1_inference(prompt, model_name, return_raw=return_raw)

        elif inference_platform == "litellm":
            return self.litellm_inference(prompt, model_name, return_raw=return_raw)

        else:
            raise ValueError(f"Unknown inference platform: {inference_platform}")
            


def get_model_platform(model_name):    
    for platform in args.all_platforms:
        all_models = getattr(args, platform)
        if model_name in all_models:
            return platform
            
    print(f'{model_name} not available')
    return None


def clean_string(text: str) -> str:
    """
    Removes special characters (like *, tabs, etc.) and trims extra spaces.
    """
    # Remove everything except alphanumerics, spaces, and hyphens/underscores
    cleaned = re.sub(r'[^A-Za-z0-9\s\-_]', '', text)
    # Normalize multiple spaces/tabs into a single space
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned




def process_inference_json(output: str):
    """
    Extracts and returns the last valid JSON object or list from a given text.
    """
    # Regex to capture JSON arrays or objects
    json_pattern = r'(\{.*?\}|\[.*?\])'
    last_valid = "Invalid Output!"

    try:
        matches = re.findall(json_pattern, output, flags=re.DOTALL)
        
    except TypeError:
            return "Invalid Output!"
        
    
    for match in matches:
        try:
            parsed = json.loads(match)
            last_valid = parsed
        except json.JSONDecodeError:
            continue  # Skip invalid matches

        
    
    return last_valid




def update_file_name(filename, pred_folder="./saved_data/inference/", extension=".csv"):
    """
    Updates the file name based on the current contents of the given directory -> Avoids overwriting
    ----------
    Parameters
    ----------
    filename: string
    Specified file name
    
    log_path: string
    Specified data directory 
    ----------
    Returns the generated text
    """
    
    folder_content = list(os.listdir(pred_folder))
    run = 1
    
    while filename.split(extension)[0]+str(run)+extension in folder_content:
        run = run+1
            
    return filename.split(extension)[0]+str(run)+extension

def validate_api_endpoints(args=args, platform=args.platform):
    """
    Checks if the mentioned model name has a corresponding api endpoint defined or not
    Returns: [List] model names (if successfully validated)
    """

    # Available Endpoints 
    available_end_points = getattr(api_endpoints, f'active_models_{platform}')
    available_models = list(available_end_points.keys())

    ## List Provided in args
    model_names = getattr(args, args.platform)
    
    for model_name in model_names:
        assert model_name in available_models, f"The API Endpoint for {model_name} not available for {args.platform}!\nPlease add the relevant details in api_endpoints.py"
    
    print("API Endpoints Validated successfully!")

    return model_names
    

def create_save_directories(saving_path=args.saving_path, evaluation_data_path=args.evaluation_data_path):
    # Extract the base directory from one of the paths
    base_dir = os.path.commonpath([saving_path, evaluation_data_path])
    
    # Check if base directory exists, if not create it
    if not os.path.exists(base_dir):
        os.makedirs(base_dir)
        print(f"Created base directory: {base_dir}")
    else:
        print(f"Base directory already exists: {base_dir}")

    # List of subdirectories to create
    sub_dirs = [evaluation_data_path, saving_path]

    # Create subdirectories
    for sub_dir_path in sub_dirs:
        if not os.path.exists(sub_dir_path):
            os.makedirs(sub_dir_path)
            print(f"Created subdirectory: {sub_dir_path}")
        else:
            print(f"Subdirectory already exists: {sub_dir_path}")



def ensure_exp_dirs_exist(saving_path: str) -> str:
    """ Verification and creation for experiments related directories"""
    
    if not os.path.exists(saving_path):
        os.makedirs(saving_path)
        print(f"Created directory: {saving_path}")
    else:
        print(f"Directory already exists: {saving_path}")
    
    return saving_path
    



def reload_lib(module):
    """
    Reloads a library
    ----------
    Parameters
    ----------
    module: library class
    the library to be reloaded
    ----------
    Returns None
    """
    import importlib
    importlib.reload(module)

