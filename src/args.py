class args:

    ## Credentials
    llm_provider_1_API_KEY = "...."
    credentials_watsonx = {
        "url": "....",
        "apikey": "...."
    }

    litellm_api_key = ""



    ## Paths
    saving_path = "./saved_data/inference/"
    evaluation_data_path = "./saved_data/evaluation_results/"

    ## Input file configuration; Define the variable column and ground truth column for evaluation
    variable_column = "VarName"

    
    ## Hyperparameters
    temperature = 0.0
    top_p = 1
    max_tokens = 16384

    
    all_platforms = ["llm_provider_1", "litellm"]

    
    ## Select the platform by changing the index of this list
    platform = ["llm_provider_1", "litellm"][0]

    
    # Model Names
    ## For llm_provider_1
    llm_provider_1 = ["llama3_3_70b", 'gpt_oss_120b', 'gpt_oss_20b',  "qwen_3_8B", 'llama4_17b_16e', "qwen_3_30b_a3b_thinking", "gemma_4_31B_it"]
    

    litellm = ["claude_sonnet_4_5"]