import pandas as pd
from typing import Dict, List, Optional


class SnippetCreation:
    """
    Creates COBOL-style code snippets from variable definitions stored in a pandas DataFrame.
    
    Expected DataFrame columns:
    - var_id: int - Unique identifier for the variable
    - var_name: str - Name of the variable
    - pic: str - COBOL PICTURE clause (can be empty)
    - sz_values: str - VALUE clause (can be empty)
    - i_level: int - COBOL level number
    - father: int - Parent variable ID (for hierarchical structure)
    """
    
    def __init__(self):
        """Initialize the snippet creation object with an empty record-to-definition mapping."""
        self.record_to_definition: Dict[int, str] = {}
    
    def print_record_definition(self, var_id: Optional[int] = None) -> None:
        """
        Print the code definition(s).
        
        Args:
            var_id: Optional variable ID. If provided, prints only that definition.
                   If None, prints all definitions.
        """
        if var_id is not None:
            if var_id in self.record_to_definition:
                print(self.record_to_definition[var_id])
            else:
                print(f"No definition found for variable ID: {var_id}")
        else:
            for key, value in self.record_to_definition.items():
                print(f"{key}\n{value}")
    
    def get_record_definition(self, var_id: int) -> str:
        """
        Get the code definition for a specific variable ID.
        
        Args:
            var_id: Variable ID to retrieve
            
        Returns:
            Code definition string, or empty string if not found
        """
        return self.record_to_definition.get(var_id, "")
    
    def _get_definition_recursive(self, df: pd.DataFrame, var_id: int, offset: int) -> str:
        """
        Recursively build the code definition for a variable and its children.
        
        Args:
            df: DataFrame containing all variable definitions
            var_id: Current variable ID to process
            offset: Indentation offset (number of spaces)
            
        Returns:
            Formatted code definition string
        """
        result = ""
        
        # Get records matching the current variable ID
        records = df[df['var_id'] == var_id]
        
        for _, obj in records.iterrows():
            obj_name = obj['var_name']
            pic = str(obj['pic']) if pd.notna(obj['pic']) else ""
            sz_val = str(obj['sz_values']) if pd.notna(obj['sz_values']) else ""
            level = int(obj['i_level'])
            
            # Build the line with proper formatting
            result += " " * offset
            result += f"{level:02d}"  # Format level as 2-digit number
            result += " " * 4
            result += obj_name
            
            if pic:
                result += " " * 4 + "PIC " + pic
            
            if sz_val:
                result += " " * 4 + "VALUE " + sz_val
            
            result += ".\n"
        
        # Get all child variables (where father == current var_id)
        children = df[df['father'] == var_id]
        
        for _, child in children.iterrows():
            child_id = int(child['var_id'])
            result += self._get_definition_recursive(df, child_id, offset + 4)
        
        return result
    
    def _filter_based_on_depth(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Filter variables to get only the top-level (root) variables.
        Root variables are those that don't have a parent (father is NaN or -1).
        
        Args:
            df: DataFrame containing all variable definitions
            
        Returns:
            Filtered DataFrame containing only root variables
        """
        # Filter for root variables (no parent or father == -1)
        root_variables = df[
            (df['father'].isna()) | 
            (df['father'] == -1) |
            (~df['father'].isin(df['var_id']))
        ]
        return root_variables
    
    def create_snippets(self, df: pd.DataFrame) -> Dict[int, str]:
        """
        Create code snippets for all root variables in the DataFrame.
        
        Args:
            df: DataFrame containing variable definitions with columns:
                - var_id: int
                - var_name: str
                - pic: str
                - sz_values: str
                - i_level: int
                - father: int
        
        Returns:
            Dictionary mapping variable IDs to their code definitions
        """
        # Validate required columns
        required_columns = ['var_id', 'var_name', 'pic', 'sz_values', 'i_level', 'father']
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            raise ValueError(f"DataFrame is missing required columns: {missing_columns}")
        
        # Clear existing definitions
        self.record_to_definition.clear()
        
        # Filter to get root variables
        filtered_variables = self._filter_based_on_depth(df)
        
        # Create snippets for each root variable
        for _, obj in filtered_variables.iterrows():
            var_id = int(obj['var_id'])
            offset = 4  # Initial indentation
            data_definition = self._get_definition_recursive(df, var_id, offset)
            self.record_to_definition[var_id] = data_definition
        
        return self.record_to_definition
    
    def get_all_definitions(self) -> Dict[int, str]:
        """
        Get all generated code definitions.
        
        Returns:
            Dictionary mapping variable IDs to their code definitions
        """
        return self.record_to_definition.copy()


def create_snippets_from_dataframe(df: pd.DataFrame) -> Dict[int, str]:
    """
    Convenience function to create code snippets from a DataFrame.
    
    Args:
        df: DataFrame containing variable definitions
        
    Returns:
        Dictionary mapping variable IDs to their code definitions
        
    Example:
        >>> import pandas as pd
        >>> data = {
        ...     'var_id': [1, 2, 3],
        ...     'var_name': ['RECORD-1', 'FIELD-A', 'FIELD-B'],
        ...     'pic': ['', 'X(10)', '9(5)'],
        ...     'sz_values': ['', '', '00000'],
        ...     'i_level': [1, 5, 5],
        ...     'father': [-1, 1, 1]
        ... }
        >>> df = pd.DataFrame(data)
        >>> snippets = create_snippets_from_dataframe(df)
        >>> print(snippets[1])
    """
    snippet_creator = SnippetCreation()
    return snippet_creator.create_snippets(df)
