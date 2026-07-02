"""
K-Hop Variable Batching Module - OPTIMIZED VERSION"""

import os
from typing import List, Dict, Any, Set, Tuple, Optional, cast
import logging
from static_analyzer_path_resolver import resolve_path

try:
    import pymssql
except ImportError:
    raise ImportError(
        "pymssql is required. Install it with: pip install pymssql"
    )


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)



# ============================================================================
# Column name mapping: internal snake_case keys → final output column names
# ============================================================================

COLUMN_MAPPING = {
    # Direct matches (casing only)
    "PATHSTR":          "PATHSTR",
    "corrected_path":   "corrected_path",
    "PIC":              "PIC",
    "szValues":         "szValues",
    "iLevel":           "iLevel",
    "Father":           "Father",
    "VarID":            "VarID",
    "Type":             "Type",
    "IsField":          "IsField",

    # Renamed
    "variable_name":    "VarName",
    "para_id":          "ParaID",
    "para_name":        "ParaName",
    "ProgramID":        "ProgID",
    "program_name":     "ProgramName",
    "para_start_row":   "ParaStartRow",
    "para_end_row":     "ParaEndRow",
    "para_start_col":   "ParaStartCol",
    "para_end_col":     "ParaEndCol",
}

# ============================================================================
# Database Connection Class (Embedded)
# ============================================================================

class DatabaseConnection:
    """
    Manages MSSQL database connections using pymssql.
    
    Configuration is hardcoded for standalone usage.
    """
    
    # Configuration loaded from environment variables
    DB_SERVER   = os.environ.get("DB_SERVER", "")
    DB_PORT     = int(os.environ.get("DB_PORT", "1433"))
    DB_USERNAME = os.environ.get("DB_USERNAME", "")
    DB_PASSWORD = os.environ.get("DB_PASSWORD", "")
    DB_TIMEOUT = 60
    
    def __init__(self):
        """Initialize database connection manager with hardcoded config."""
        self._connection: Optional[pymssql.Connection] = None
        logger.info("DatabaseConnection initialized with hardcoded config")
    
    def connect(self) -> pymssql.Connection:
        """
        Establish connection to the database.
        
        Returns:
            Active database connection
            
        Raises:
            pymssql.Error: If connection fails
        """
        try:
            if self._connection is None:
                logger.info("Establishing new database connection")
                connection = pymssql.connect(
                    server=self.DB_SERVER,
                    port=str(self.DB_PORT),
                    user=self.DB_USERNAME,
                    password=self.DB_PASSWORD,
                    timeout=self.DB_TIMEOUT,
                    login_timeout=self.DB_TIMEOUT
                )
                self._connection = cast(pymssql.Connection, connection)
                logger.info("Database connection established successfully")
            return cast(pymssql.Connection, self._connection)
        except pymssql.Error as e:
            logger.error(f"Failed to connect to database: {e}")
            raise
    
    def close(self) -> None:
        """Close the database connection."""
        if self._connection is not None:
            try:
                self._connection.close()
                logger.info("Database connection closed")
            except pymssql.Error as e:
                logger.error(f"Error closing connection: {e}")
            finally:
                self._connection = None


# ============================================================================
# K-Hop Variable Discovery Functions - OPTIMIZED
# ============================================================================


def get_related_variables_by_statement(
    database_name: str,
    input_variable_names: List[str]
) -> List[Dict[str, Any]]:
    """
    Find variables that co-occur with specified input variables in COBOL MOVE statements.

    This query performs a Cartesian join to find all variables that appear in the same
    MOVE statements as the input variables, enriched with paragraph, path, and full
    variable-declaration occurrence data.

    Args:
        database_name: Name of the database to query
        input_variable_names: List of variable names to find relationships for

    Returns:
        List of dictionaries containing:
        - ProgramName, ProgramID: Program identifiers
        - ParaID, ParaName: Paragraph the statement belongs to
        - ParaOccurID, ParaOccOccurID: Paragraph occurrence IDs
        - ParaStartRow, ParaEndRow, ParaStartCol, ParaEndCol: Paragraph block bounds
        - Description: Statement description ('COBOL: MOVE …')
        - StartLine, EndLine: Statement line range in the program
        - PathID, PATHSTR: Execution path identifier and string
        - InputVariable: The input variable name searched for
        - RelatedVariable: Variable that co-occurs in the same statement
        - VarID, Type, IsField, IsCopy: Variable type metadata
        - Father, Ancestor, Redefines, Redefined: Variable hierarchy fields
        - PIC, szValues, iLevel, NumOfChilds: Variable definition details
        - VarOccurID: OccurID stored on the variable row (declaration reference)
        - VarOccOccurID: OccurID from the Occurrences table for the variable declaration
        - VarStartRow, VarEndRow, VarStartCol, VarEndCol: Variable declaration bounds
        - ResourceID, ResourceType: StatementReference identifiers
        - bRead: Whether the variable was read (1) or written (0) in the statement
    """
    if not input_variable_names:
        return []
    
    # Build parameterized placeholders for IN clause
    var_placeholders = ','.join(['%s'] * len(input_variable_names))
    
    query =  f"""......THIS QUERY FETCHES THE STATIC ANALYSIS DATA......."""
    
    db = DatabaseConnection()
    try:
        connection = db.connect()
        cursor = connection.cursor()
        
        # Switch to the specified database
        cursor.execute(f"USE [{database_name}]")
        
        # Execute the query with variable names as parameters
        params = tuple(input_variable_names)
        cursor.execute(query, params)
        
        # Fetch all results
        if cursor.description is None:
            cursor.close()
            return []
        
        columns = [column[0] for column in cursor.description]
        results = []
        for row in cursor.fetchall():
            results.append(dict(zip(columns, row)))
        
        cursor.close()
        return results
        
    finally:
        db.close()


def get_k_hop_variable_batching_optimized(
    input_variables: List[str],
    num_hops: int,
    database_name: str
) -> Dict[str, Dict[str, Any]]:
    """
    OPTIMIZED: Perform k-hop variable relationship discovery with minimal database queries.
    
    Key Optimization:
    - Makes only num_hops database queries per application (not per variable)
    - Queries ALL variables together at each hop level
    - Distributes results back to individual variables after querying
    
    Example for 108 variables with 2 hops:
    - Original approach: 216 queries (108 variables × 2 hops)
    - Optimized approach: 2 queries (1 per hop level)
    
    Algorithm:
    1. Hop 1: Query ALL input variables at once → Get all hop-1 relationships
    2. Distribute hop-1 results to each input variable
    3. Hop 2: Query ALL hop-1 variables at once → Get all hop-2 relationships
    4. Distribute hop-2 results to each input variable
    5. Continue for num_hops
    
    Args:
        input_variables: List of variable names to start discovery from
        num_hops: Number of hops to traverse (must be >= 1)
        database_name: Name of the database application to query
    
    Returns:
        Dictionary mapping each input variable to its k-hop discovery results
    """
    if num_hops < 1:
        raise ValueError("num_hops must be at least 1")
    
    if not input_variables:
        return {}
    
    print(f"\n{'='*100}")
    print(f"OPTIMIZED K-HOP DISCOVERY: {len(input_variables)} variables, {num_hops} hops")
    print(f"Database queries: {num_hops} (instead of {len(input_variables) * num_hops})")
    print(f"{'='*100}")
    
    # Initialize result structure for each input variable
    results = {}
    for var in input_variables:
        results[var] = {
            'total_variables': 0,
            'hops': {},
            'all_related_variables': [],
            'relationships': []
        }
    
    # Track what variables each input variable has seen (local deduplication per input var)
    variable_seen_map = {var: {var} for var in input_variables}
    
    # Track parent variables for each input variable (to avoid backtracking)
    variable_parent_map = {var: set() for var in input_variables}
    
    # Track which variables to query at each hop for each input variable
    # Format: {input_var: [variables_to_query_for_this_input]}
    variable_current_hop_map = {var: [var] for var in input_variables}
    
    # Perform k-hop discovery
    hop_num = 0
    for hop_num in range(1, num_hops + 1):
        print(f"\n{'─'*100}")
        print(f"HOP {hop_num}: Processing all variables together")
        print(f"{'─'*100}")
        
        # Collect ALL unique variables to query across all input variables
        all_vars_to_query = set()
        for input_var in input_variables:
            if variable_current_hop_map[input_var]:
                all_vars_to_query.update(variable_current_hop_map[input_var])
        
        if not all_vars_to_query:
            print(f"No variables to query for hop {hop_num}. Stopping.")
            break
        
        all_vars_to_query_list = sorted(list(all_vars_to_query))
        print(f"Querying {len(all_vars_to_query_list)} unique variables in a SINGLE database call...")
        
        # SINGLE DATABASE QUERY for all variables at this hop level
        related_results = get_related_variables_by_statement(
            database_name=database_name,
            input_variable_names=all_vars_to_query_list
        )
        
        print(f"✓ Found {len(related_results)} relationship records")
        
        # Build a mapping: input_var -> related_vars for quick lookup
        # This helps us distribute results back to each input variable
        hop_relationships = {}
        for result in related_results:
            from_var = result['InputVariable']
            to_var = result['RelatedVariable']
            
            if from_var not in hop_relationships:
                hop_relationships[from_var] = []
            hop_relationships[from_var].append(result)
        
        # Now distribute results to each input variable
        print(f"Distributing results to {len(input_variables)} input variables...")
        
        for input_var in input_variables:
            # Get variables we queried for this input variable at this hop
            queried_vars = variable_current_hop_map[input_var]
            
            if not queried_vars:
                continue
            
            # Collect new variables discovered for this input variable
            hop_variables = set()
            
            for queried_var in queried_vars:
                if queried_var in hop_relationships:
                    for result in hop_relationships[queried_var]:
                        related_var = result['RelatedVariable']
                        
                        # Skip if already seen for this input variable
                        if related_var in variable_seen_map[input_var]:
                            continue
                        
                        # Skip parent variables (optimization)
                        if related_var in variable_parent_map[input_var]:
                            continue
                        
                        # Add to this hop's variables
                        hop_variables.add(related_var)
                        variable_seen_map[input_var].add(related_var)
                        
                        # Store relationship — keys follow COLUMN_MAPPING values
                        results[input_var]['relationships'].append({
                            'hop': hop_num,
                            'from_variable': result['InputVariable'],
                            'VarName': related_var,
                            # Program
                            'ProgramName': result['ProgramName'],
                            'ProgID': result['ProgramID'],
                            # Paragraph
                            'ParaID': result['ParaID'],
                            'ParaName': result['ParaName'],
                            'para_occur_id': result['ParaOccurID'],
                            'para_occ_occur_id': result['ParaOccOccurID'],
                            'ParaStartRow': result['ParaStartRow'],
                            'ParaEndRow': result['ParaEndRow'],
                            'ParaStartCol': result['ParaStartCol'],
                            'ParaEndCol': result['ParaEndCol'],
                            # Statement
                            'statement': result['Description'],
                            'start_line': result['StartLine'],
                            'end_line': result['EndLine'],
                            # Path
                            'path_id': result['PathID'],
                            'PATHSTR': result['PATHSTR'],
                            # Variable metadata
                            'VarID': result['VarID'],
                            'Type': result['Type'],
                            'IsField': result['IsField'],
                            'is_copy': result['IsCopy'],
                            'Father': result['Father'],
                            'ancestor': result['Ancestor'],
                            'redefines': result['Redefines'],
                            'redefined': result['Redefined'],
                            'PIC': result['PIC'],
                            'szValues': result['szValues'],
                            'iLevel': result['iLevel'],
                            'num_of_childs': result['NumOfChilds'],
                            # Variable occurrence (declaration bounds)
                            'var_occur_id': result['VarOccurID'],
                            'var_occ_occur_id': result['VarOccOccurID'],
                            'var_start_row': result['VarStartRow'],
                            'var_end_row': result['VarEndRow'],
                            'var_start_col': result['VarStartCol'],
                            'var_end_col': result['VarEndCol'],
                            # Statement reference
                            'resource_id': result['ResourceID'],
                            'resource_type': result['ResourceType'],
                            'b_read': result['bRead'],
                        })
            
            # Store hop results for this input variable
            hop_variables_list = sorted(list(hop_variables))
            if hop_variables_list:
                results[input_var]['hops'][hop_num] = hop_variables_list
                results[input_var]['all_related_variables'].extend(hop_variables_list)
            
            # Update parent variables for next hop
            variable_parent_map[input_var] = set(queried_vars)
            
            # Prepare for next hop
            variable_current_hop_map[input_var] = hop_variables_list
        
        # Count how many input variables still have variables to process
        active_count = sum(1 for v in input_variables if variable_current_hop_map[v])
        print(f"✓ Hop {hop_num} complete. {active_count}/{len(input_variables)} variables have more to discover.")
    
    # Update total counts
    for input_var in input_variables:
        results[input_var]['total_variables'] = len(results[input_var]['all_related_variables'])
    
    print(f"\n{'='*100}")
    print(f"OPTIMIZED K-HOP DISCOVERY COMPLETE")
    print(f"Total database queries: {hop_num} (saved {len(input_variables) * num_hops - hop_num} queries!)")
    print(f"{'='*100}")
    
    return results


def print_k_hop_summary(results: Dict[str, Dict[str, Any]]) -> None:
    """
    Print a formatted summary of k-hop discovery results.
    
    Args:
        results: Output from get_k_hop_variable_batching_optimized
    """
    print("\n" + "="*100)
    print("K-HOP VARIABLE DISCOVERY SUMMARY")
    print("="*100)
    
    for input_var, data in results.items():
        print(f"\n{'─'*100}")
        print(f"Input Variable: {input_var}")
        print(f"{'─'*100}")
        print(f"Total Related Variables: {data['total_variables']}")
        
        if data['hops']:
            print("\nVariables by Hop:")
            for hop_num in sorted(data['hops'].keys()):
                hop_vars = data['hops'][hop_num]
                print(f"  Hop {hop_num}: {len(hop_vars)} variables")
                # Print first 5 variables as sample
                sample_vars = hop_vars[:5]
                for var in sample_vars:
                    print(f"    - {var}")
                if len(hop_vars) > 5:
                    print(f"    ... and {len(hop_vars) - 5} more")
        
        print(f"\nTotal Relationships Tracked: {len(data['relationships'])}")
    
    print("\n" + "="*100)


# ============================================================================
# Helper Functions for Main Driver
# ============================================================================

def setup_configuration():
    """
    Setup configuration parameters for k-hop discovery.
    
    Returns:
        dict: Configuration dictionary with all necessary parameters
    """
    from pathlib import Path
    
    # Hardcoded AppName to Database mapping (from Metadata.xlsx columns J and L)
    app_to_db_map = {
        "CARDDEMO": "EZ_carddemo",
        "COBCURSES": "EZ_COBCURSES",
        "COBSOFT": "EZ_COBSOFT",
        "CRYPTOCOB": "EZ_CRYPTOCOB",
        "DEBINIX": "EZ_DEBINIX",
        "DGFIP": "EZ_DGFIP",
        "ETALAB": "EZ_ETALAB",
        "FIZZBUZZ": "EZ_FIZZBUZZ",
        "GENAPP": "EZ_genappdb2",
        "IBM_idz": "EZ_IDZUTIL",
        "IBM_zOS": "EZ_ZOSCLIENT",
        "LASERVIK": "EZ_LASERVIK",
        "LEARNING": "EZ_LEARNING",
        "MORTGAGE": "EZ_MORTAGAGE",
        "Z390DEV": "EZ_ZDEV",
        "ZECS": "EZ_ZECS",
    }
    
    config = {
        'csv_path': "./data/batched_data/record/batched_data_record_25June2026.csv",
        'num_hops': 2,
        'case': "MoveStmnt",
        'output_dir': Path("./data/batched_data/k_hop"),
        'app_to_db_map': app_to_db_map
    }
    
    # Create output directory
    config['output_dir'].mkdir(exist_ok=True)
    
    return config


def load_csv_data(csv_path: str, app_to_db_map: Dict[str, str]) -> Tuple[List[Dict], List[str], List[Dict]]:
    """
    Load CSV data and map variables to databases.
    
    Args:
        csv_path: Path to input CSV file
        app_to_db_map: Mapping of application names to database names
        
    Returns:
        Tuple of (original_rows, fieldnames, data_rows)
    """
    import csv
    from pathlib import Path
    
    if not Path(csv_path).exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")
    
    # Increase CSV field size limit for large fields
    csv.field_size_limit(10000000)
    
    # Read CSV file
    original_rows = []
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames if reader.fieldnames else [])
        for row in reader:
            original_rows.append(row)
    
    # Extract and map data
    data_rows = []
    skipped_count = 0
    
    for row in original_rows:
        var_name = row.get('variable_name', '').strip()
        application = row.get('app_name', '').strip()
        
        if var_name and application:
            database = app_to_db_map.get(application)
            if database:
                data_rows.append({
                    'variable_name': var_name,
                    'app_name': application,
                    'database': database,
                    'original_row': row
                })
            else:
                skipped_count += 1
                logger.warning(f"Unknown application '{application}' for variable '{var_name}'")
    
    if skipped_count > 0:
        print(f"  Skipped {skipped_count} rows with unknown applications")
    
    return original_rows, fieldnames, data_rows


def group_by_application(data_rows: List[Dict]) -> Dict[str, Dict]:
    """
    Group variables by application.
    
    Args:
        data_rows: List of data rows with variable, application, database info
        
    Returns:
        Dictionary mapping application name to {database, variables}
    """
    app_groups = {}
    for row in data_rows:
        app = row['app_name']
        db = row['database']
        var = row['variable_name']
        
        if app not in app_groups:
            app_groups[app] = {
                'database': db,
                'variables': []
            }
        app_groups[app]['variables'].append(var)
    
    return app_groups


def process_k_hop_discovery_optimized(app_groups: Dict[str, Dict], num_hops: int) -> Tuple[Dict, Dict]:
    """
    OPTIMIZED: Run k-hop discovery for all application groups.
    
    Makes only num_hops queries per application instead of num_variables * num_hops.
    
    Args:
        app_groups: Dictionary of application groups
        num_hops: Number of hops for discovery
        
    Returns:
        Tuple of (all_results, variable_to_batch)
    """
    import time
    
    all_results = {}
    variable_to_batch = {}
    
    print(f"\nProcessing {len(app_groups)} applications with {num_hops}-hop discovery...")
    print(f"OPTIMIZED MODE: Only {num_hops} database queries per application")
    print("="*100)
    
    for app_name, app_data in sorted(app_groups.items()):
        database = app_data['database']
        variables = app_data['variables']
        
        print(f"\n{'#'*100}")
        print(f"# Processing: {app_name} ({database}) - {len(variables)} variables")
        print(f"# Database queries for this app: {num_hops} (vs {len(variables) * num_hops} in original)")
        print(f"{'#'*100}")
        
        try:
            # OPTIMIZED: Process ALL variables at once
            app_results = get_k_hop_variable_batching_optimized(
                input_variables=variables,
                num_hops=num_hops,
                database_name=database
            )
            
            # Identify isolated variables (no related variables found)
            isolated_variables = []
            
            # Create batch for each variable
            for var_idx, var_name in enumerate(variables):
                if var_name in app_results:
                    # Build a lookup: related_variable_name -> first relationship record that describes it
                    rel_lookup = {}
                    for rel in app_results[var_name]['relationships']:
                        rv = rel['VarName']
                        if rv not in rel_lookup:
                            rel_lookup[rv] = rel

                    # Find the first relationship where the input variable itself was the
                    # RelatedVariable (i.e. from_variable != var_name but to_variable ==
                    # var_name), OR where it was the InputVariable — either way the DB row
                    # for that variable carries all its own metadata as v_other.
                    # We look it up from rel_lookup directly: the input variable will appear
                    # as to_variable in some hop-2+ result, or we can pull the first
                    # relationship record's context fields since they all share the same
                    # program/para/path for a given occurrence.
                    # Most reliable: scan all relationships for one where from_variable is
                    # var_name — the first such record has the input var as InputVariable so
                    # its program/para/path context is valid; its v_other fields don't apply.
                    # Instead we need the row where RelatedVariable IS var_name.
                    # That is stored in rel_lookup[var_name] if it was ever a related var.
                    self_rel = rel_lookup.get(var_name)

                    # Seed entry for the input variable itself, populated from DB if available
                    # Keys follow COLUMN_MAPPING values
                    batch_dicts = [{
                        'VarName':           var_name,
                        'ProgramName':       self_rel.get('ProgramName')       if self_rel else None,
                        'ProgID':            self_rel.get('ProgID')            if self_rel else None,
                        'ParaID':            self_rel.get('ParaID')            if self_rel else None,
                        'ParaName':          self_rel.get('ParaName')          if self_rel else None,
                        'para_occur_id':     self_rel.get('para_occur_id')     if self_rel else None,
                        'para_occ_occur_id': self_rel.get('para_occ_occur_id') if self_rel else None,
                        'ParaStartRow':      self_rel.get('ParaStartRow')      if self_rel else None,
                        'ParaEndRow':        self_rel.get('ParaEndRow')        if self_rel else None,
                        'ParaStartCol':      self_rel.get('ParaStartCol')      if self_rel else None,
                        'ParaEndCol':        self_rel.get('ParaEndCol')        if self_rel else None,
                        'statement':         self_rel.get('statement')         if self_rel else None,
                        'start_line':        self_rel.get('start_line')        if self_rel else None,
                        'end_line':          self_rel.get('end_line')          if self_rel else None,
                        'path_id':           self_rel.get('path_id')           if self_rel else None,
                        'PATHSTR':           self_rel.get('PATHSTR')           if self_rel else None,
                        'VarID':             self_rel.get('VarID')             if self_rel else None,
                        'Type':              self_rel.get('Type')              if self_rel else None,
                        'IsField':           self_rel.get('IsField')           if self_rel else None,
                        'is_copy':           self_rel.get('is_copy')           if self_rel else None,
                        'Father':            self_rel.get('Father')            if self_rel else None,
                        'ancestor':          self_rel.get('ancestor')          if self_rel else None,
                        'redefines':         self_rel.get('redefines')         if self_rel else None,
                        'redefined':         self_rel.get('redefined')         if self_rel else None,
                        'PIC':               self_rel.get('PIC')               if self_rel else None,
                        'szValues':          self_rel.get('szValues')          if self_rel else None,
                        'iLevel':            self_rel.get('iLevel')            if self_rel else None,
                        'num_of_childs':     self_rel.get('num_of_childs')     if self_rel else None,
                        'var_occur_id':      self_rel.get('var_occur_id')      if self_rel else None,
                        'var_occ_occur_id':  self_rel.get('var_occ_occur_id')  if self_rel else None,
                        'var_start_row':     self_rel.get('var_start_row')     if self_rel else None,
                        'var_end_row':       self_rel.get('var_end_row')       if self_rel else None,
                        'var_start_col':     self_rel.get('var_start_col')     if self_rel else None,
                        'var_end_col':       self_rel.get('var_end_col')       if self_rel else None,
                        'resource_id':       self_rel.get('resource_id')       if self_rel else None,
                        'resource_type':     self_rel.get('resource_type')     if self_rel else None,
                        'b_read':            self_rel.get('b_read')            if self_rel else None,
                        'corrected_path':    resolve_path(self_rel.get('PATHSTR')) if self_rel and self_rel.get('PATHSTR') else None,
                    }]

                    for rv in app_results[var_name]['all_related_variables']:
                        rel = rel_lookup.get(rv, {})
                        batch_dicts.append({
                            'VarName':           rv,
                            'ProgramName':       rel.get('ProgramName'),
                            'ProgID':            rel.get('ProgID'),
                            'ParaID':            rel.get('ParaID'),
                            'ParaName':          rel.get('ParaName'),
                            'para_occur_id':     rel.get('para_occur_id'),
                            'para_occ_occur_id': rel.get('para_occ_occur_id'),
                            'ParaStartRow':      rel.get('ParaStartRow'),
                            'ParaEndRow':        rel.get('ParaEndRow'),
                            'ParaStartCol':      rel.get('ParaStartCol'),
                            'ParaEndCol':        rel.get('ParaEndCol'),
                            'statement':         rel.get('statement'),
                            'start_line':        rel.get('start_line'),
                            'end_line':          rel.get('end_line'),
                            'path_id':           rel.get('path_id'),
                            'PATHSTR':           rel.get('PATHSTR'),
                            'VarID':             rel.get('VarID'),
                            'Type':              rel.get('Type'),
                            'IsField':           rel.get('IsField'),
                            'is_copy':           rel.get('is_copy'),
                            'Father':            rel.get('Father'),
                            'ancestor':          rel.get('ancestor'),
                            'redefines':         rel.get('redefines'),
                            'redefined':         rel.get('redefined'),
                            'PIC':               rel.get('PIC'),
                            'szValues':          rel.get('szValues'),
                            'iLevel':            rel.get('iLevel'),
                            'num_of_childs':     rel.get('num_of_childs'),
                            'var_occur_id':      rel.get('var_occur_id'),
                            'var_occ_occur_id':  rel.get('var_occ_occur_id'),
                            'var_start_row':     rel.get('var_start_row'),
                            'var_end_row':       rel.get('var_end_row'),
                            'var_start_col':     rel.get('var_start_col'),
                            'var_end_col':       rel.get('var_end_col'),
                            'resource_id':       rel.get('resource_id'),
                            'resource_type':     rel.get('resource_type'),
                            'b_read':            rel.get('b_read'),
                            'corrected_path':    resolve_path(rel.get('PATHSTR')) if rel.get('PATHSTR') else None,
                        })

                    variable_to_batch[var_name] = batch_dicts

                    # Check if isolated (no related variables)
                    if app_results[var_name]['total_variables'] == 0:
                        isolated_variables.append(var_name)
                else:
                    # Variable not in results - treat as isolated
                    # Still create batch with just the variable itself
                    _empty = {'VarName': var_name,
                              'ProgramName': None, 'ProgID': None,
                              'ParaID': None, 'ParaName': None,
                              'para_occur_id': None, 'para_occ_occur_id': None,
                              'ParaStartRow': None, 'ParaEndRow': None,
                              'ParaStartCol': None, 'ParaEndCol': None,
                              'statement': None,
                              'start_line': None, 'end_line': None,
                              'path_id': None, 'PATHSTR': None,
                              'VarID': None, 'Type': None, 'IsField': None,
                              'is_copy': None, 'Father': None, 'ancestor': None,
                              'redefines': None, 'redefined': None,
                              'PIC': None, 'szValues': None, 'iLevel': None,
                              'num_of_childs': None,
                              'var_occur_id': None, 'var_occ_occur_id': None,
                              'var_start_row': None, 'var_end_row': None,
                              'var_start_col': None, 'var_end_col': None,
                              'resource_id': None, 'resource_type': None,
                              'b_read': None,
                              'corrected_path': None}
                    variable_to_batch[var_name] = [_empty]
                    isolated_variables.append(var_name)

                    # Add to results as isolated variable
                    app_results[var_name] = {
                        'total_variables': 0,
                        'hops': {},
                        'all_related_variables': [],
                        'relationships': [],
                        'isolated': True
                    }
            
            # Store results
            all_results[app_name] = {
                'database': database,
                'input_variable_count': len(variables),
                'successful_count': len(variables),  # All variables are now successful
                'isolated_count': len(isolated_variables),
                'isolated_variables': isolated_variables,
                'k_hop_results': app_results
            }
            
            print(f"\n✓ {app_name} completed: {len(variables)}/{len(variables)} variables")
            if isolated_variables:
                print(f"  ℹ {len(isolated_variables)} isolated variables (no co-occurring variables)")
            
        except Exception as e:
            logger.error(f"Failed processing {app_name}: {e}", exc_info=True)
            all_results[app_name] = {
                'database': database,
                'input_variable_count': len(variables),
                'error': str(e),
                'k_hop_results': {}
            }
            print(f"\n✗ {app_name} failed: {e}")
        
        # Small delay between applications
        time.sleep(0.5)
    
    return all_results, variable_to_batch


def calculate_statistics(all_results: Dict) -> Dict:
    """
    Calculate comprehensive statistics from k-hop discovery results.
    
    IMPORTANT: This function processes data that has already been prepared by
    process_k_hop_discovery_optimized(), where:
    - All input variables are in k_hop_results (including isolated ones)
    - isolated_count and isolated_variables are pre-calculated
    - successful_count = input_variable_count (all variables processed)
    
    Args:
        all_results: Dictionary of all application results
        
    Returns:
        Dictionary with statistics including distribution analysis
    """
    import statistics as stat_module
    
    stats = {
        'total_applications': len(all_results),
        'total_input_vars': 0,
        'total_successful_vars': 0,
        'total_failed_vars': 0,
        'total_isolated_vars': 0,
        'total_discovered_vars': 0,
        'total_relationships': 0,
        'per_application': {}
    }
    
    # Collect ALL variable discovery counts for distribution analysis
    # This should include every single input variable (including isolated ones with 0 discoveries)
    all_discovered_counts = []
    all_isolated_vars = []
    
    for app_name, app_result in all_results.items():
        # Handle applications that failed completely
        if 'error' in app_result:
            input_count = app_result.get('input_variable_count', 0)
            stats['per_application'][app_name] = {
                'database': app_result['database'],
                'error': app_result['error'],
                'input_count': input_count,
                'failed_count': input_count
            }
            stats['total_input_vars'] += input_count
            stats['total_failed_vars'] += input_count
            continue
        
        # Process successful applications
        k_hop_results = app_result['k_hop_results']
        input_count = app_result['input_variable_count']
        
        # Get pre-calculated counts from process_k_hop_discovery_optimized()
        successful_count = app_result.get('successful_count', len(k_hop_results))
        isolated_count = app_result.get('isolated_count', 0)
        isolated_vars = app_result.get('isolated_variables', [])
        
        # Verify data consistency
        if len(k_hop_results) != input_count:
            logger.warning(f"{app_name}: k_hop_results has {len(k_hop_results)} vars but input_count is {input_count}")
        
        # Calculate totals from k_hop_results
        # IMPORTANT: k_hop_results should contain ALL input variables (including isolated ones)
        app_discovered = 0
        app_relationships = 0
        app_isolated_actual = 0
        
        for var_name, var_data in k_hop_results.items():
            discovered_count = var_data['total_variables']
            relationship_count = len(var_data['relationships'])
            
            # Add to distribution (every variable, including isolated)
            all_discovered_counts.append(discovered_count)
            
            # Count isolated variables (those with 0 discoveries)
            if discovered_count == 0:
                app_isolated_actual += 1
                all_isolated_vars.append(var_name)
            
            app_discovered += discovered_count
            app_relationships += relationship_count
        
        # Verify isolated count matches
        if app_isolated_actual != isolated_count:
            logger.warning(f"{app_name}: Calculated {app_isolated_actual} isolated but stored {isolated_count}")
        
        # Update global stats
        stats['total_input_vars'] += input_count
        stats['total_successful_vars'] += successful_count
        stats['total_isolated_vars'] += app_isolated_actual  # Use calculated value
        stats['total_discovered_vars'] += app_discovered
        stats['total_relationships'] += app_relationships
        
        # Store per-application stats
        stats['per_application'][app_name] = {
            'database': app_result['database'],
            'input_count': input_count,
            'successful_count': successful_count,
            'failed_count': 0,  # No failures in successful apps
            'isolated_count': app_isolated_actual,  # Use calculated value
            'isolated_variables': [v for v in isolated_vars if v in k_hop_results and k_hop_results[v]['total_variables'] == 0],
            'discovered_count': app_discovered,
            'relationships_count': app_relationships,
            'avg_per_input': app_discovered / successful_count if successful_count > 0 else 0
        }
    
    # Verify total counts match
    if len(all_discovered_counts) != stats['total_successful_vars']:
        logger.warning(f"Distribution has {len(all_discovered_counts)} counts but total_successful_vars is {stats['total_successful_vars']}")
    
    # Calculate distribution statistics (variable-level)
    if all_discovered_counts:
        sorted_counts = sorted(all_discovered_counts, reverse=True)
        
        stats['distribution'] = {
            'total_variables': len(all_discovered_counts),
            'min': min(all_discovered_counts),
            'max': max(all_discovered_counts),
            'median': stat_module.median(all_discovered_counts),
            'mean': stat_module.mean(all_discovered_counts),
            'std_dev': stat_module.stdev(all_discovered_counts) if len(all_discovered_counts) > 1 else 0,
            'percentile_25': stat_module.quantiles(all_discovered_counts, n=4)[0] if len(all_discovered_counts) >= 4 else 0,
            'percentile_75': stat_module.quantiles(all_discovered_counts, n=4)[2] if len(all_discovered_counts) >= 4 else 0,
            'percentile_90': stat_module.quantiles(all_discovered_counts, n=10)[8] if len(all_discovered_counts) >= 10 else 0,
            'percentile_95': stat_module.quantiles(all_discovered_counts, n=20)[18] if len(all_discovered_counts) >= 20 else 0,
        }
        
        # Calculate concentration: what % of input variables contribute to 90% of discovered variables
        total_discovered = sum(sorted_counts)
        if total_discovered > 0:
            target_90_percent = total_discovered * 0.9
            cumulative = 0
            vars_for_90_percent = 0
            
            for count in sorted_counts:
                cumulative += count
                vars_for_90_percent += 1
                if cumulative >= target_90_percent:
                    break
            
            stats['distribution']['concentration_90_percent'] = {
                'variable_count': vars_for_90_percent,
                'percentage_of_inputs': (vars_for_90_percent / len(all_discovered_counts)) * 100,
                'description': f"{vars_for_90_percent} variables ({(vars_for_90_percent / len(all_discovered_counts)) * 100:.1f}%) contribute to 90% of all discovered variables"
            }
        
        # Count variables by discovery range
        stats['distribution']['ranges'] = {
            'zero': sum(1 for c in all_discovered_counts if c == 0),
            '1-10': sum(1 for c in all_discovered_counts if 1 <= c <= 10),
            '11-50': sum(1 for c in all_discovered_counts if 11 <= c <= 50),
            '51-100': sum(1 for c in all_discovered_counts if 51 <= c <= 100),
            '101-200': sum(1 for c in all_discovered_counts if 101 <= c <= 200),
            '200+': sum(1 for c in all_discovered_counts if c > 200)
        }
        
        # Verify: zero discoveries should equal isolated count
        zero_count = stats['distribution']['ranges']['zero']
        if zero_count != stats['total_isolated_vars']:
            logger.warning(f"Zero discoveries ({zero_count}) != total_isolated_vars ({stats['total_isolated_vars']})")
    
    return stats


def write_output_csv(original_rows: List[Dict], fieldnames: List[str],
                     variable_to_batch: Dict, config: Dict) -> str:
    """
    Write output JSON with all original row fields plus a native-list batch column.

    Args:
        original_rows: Original CSV rows
        fieldnames: Original CSV fieldnames (unused for JSON but kept for signature compatibility)
        variable_to_batch: Mapping of variable to batch list
        config: Configuration dictionary

    Returns:
        Path to output JSON file
    """
    import json as _json

    batch_column_name = f"batch_{config['num_hops']}_{config['case']}_optimized"
    output_path = config['output_dir'] / f"batched_data_record_{config['num_hops']}_{config['case']}_optimized_para_occ.json"

    records = []
    for row in original_rows:
        var_name = row.get('variable_name', '').strip()
        record = dict(row)

        curr_batch_variables = variable_to_batch.get(var_name, [])
        record[batch_column_name] = curr_batch_variables
        records.append(record)

    with open(output_path, 'w', encoding='utf-8') as f:
        _json.dump(records, f, ensure_ascii=False, indent=2)

    return str(output_path)


def write_output_json(all_results: Dict, variable_to_batch: Dict,
                      stats: Dict, config: Dict) -> str:
    """
    Write detailed JSON output.
    
    Args:
        all_results: All k-hop discovery results
        variable_to_batch: Mapping of variable to batch list
        stats: Statistics dictionary
        config: Configuration dictionary
        
    Returns:
        Path to output JSON file
    """
    import json
    from datetime import datetime
    
    output_path = config['output_dir'] / f"output_{config['num_hops']}_{config['case']}_optimized.json"
    
    output_data = {
        'metadata': {
            'timestamp': datetime.now().isoformat(),
            'num_hops': config['num_hops'],
            'case': config['case'],
            'input_csv': config['csv_path'],
            'optimization': 'Only num_hops queries per application',
            'statistics': stats
        },
        'application_results': {}
    }
    
    # Add results for each application
    for app_name, app_result in all_results.items():
        if 'error' in app_result:
            output_data['application_results'][app_name] = {
                'database': app_result['database'],
                'error': app_result['error']
            }
        else:
            output_data['application_results'][app_name] = {
                'database': app_result['database'],
                'input_variable_count': app_result['input_variable_count'],
                'isolated_count': app_result.get('isolated_count', 0),
                'isolated_variables': app_result.get('isolated_variables', []),
                'variables': {}
            }
            
            for var_name, var_data in app_result['k_hop_results'].items():
                output_data['application_results'][app_name]['variables'][var_name] = {
                    'total_variables': var_data['total_variables'],
                    'hops': var_data['hops'],
                    'all_related_variables': var_data['all_related_variables'],
                    'batch': variable_to_batch.get(var_name, []),
                    'relationship_count': len(var_data['relationships']),
                    'relationships': var_data['relationships'],
                    'isolated': var_data.get('isolated', False)
                }
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    
    return str(output_path)


def print_summary(stats: Dict, csv_path: str, json_path: str):
    """
    Print final summary of processing.
    
    Args:
        stats: Statistics dictionary
        csv_path: Path to output CSV
        json_path: Path to output JSON
    """
    from pathlib import Path
    
    print("\n" + "="*100)
    print("OPTIMIZED K-HOP DISCOVERY COMPLETE - SUMMARY")
    print("="*100)
    
    # Per-application summary
    for app_name, app_stats in sorted(stats['per_application'].items()):
        if 'error' in app_stats:
            print(f"\n❌ {app_name} ({app_stats['database']}): {app_stats['error']}")
        else:
            isolated_count = app_stats.get('isolated_count', 0)
            isolated_icon = f" (ℹ {isolated_count} isolated)" if isolated_count > 0 else ""
            print(f"\n✓ {app_name} ({app_stats['database']}):{isolated_icon}")
            print(f"  Input: {app_stats['input_count']} | "
                  f"Success: {app_stats.get('successful_count', app_stats['input_count'])} | "
                  f"Isolated: {isolated_count}")
            print(f"  Discovered: {app_stats['discovered_count']} | "
                  f"Relationships: {app_stats['relationships_count']} | "
                  f"Avg: {app_stats['avg_per_input']:.1f}")
            if isolated_count > 0 and isolated_count <= 5:
                isolated_vars = app_stats.get('isolated_variables', [])
                print(f"  Isolated vars: {', '.join(isolated_vars)}")
            elif isolated_count > 5:
                isolated_vars = app_stats.get('isolated_variables', [])
                print(f"  Isolated vars: {', '.join(isolated_vars[:5])} ... and {isolated_count - 5} more")
    
    # Overall statistics
    print("\n" + "="*100)
    print("OVERALL STATISTICS:")
    print("="*100)
    print(f"Applications Processed: {stats['total_applications']}")
    print(f"Total Input Variables: {stats['total_input_vars']}")
    print(f"Successfully Processed: {stats.get('total_successful_vars', stats['total_input_vars'])} (100%)")
    isolated = stats.get('total_isolated_vars', 0)
    total_input = stats['total_input_vars']
    isolated_pct = (isolated / total_input * 100) if total_input > 0 else 0.0
    print(f"Isolated Variables: {isolated} ({isolated_pct:.1f}%)")
    print(f"Total Discovered Variables: {stats['total_discovered_vars']}")
    print(f"Total Relationships: {stats['total_relationships']}")
    
    # Distribution statistics (variable-level)
    if 'distribution' in stats:
        dist = stats['distribution']
        print("\n" + "="*100)
        print("DISCOVERED VARIABLES DISTRIBUTION (PER VARIABLE):")
        print("="*100)
        print(f"Minimum: {dist['min']}")
        print(f"Maximum: {dist['max']}")
        print(f"Median: {dist['median']:.1f}")
        print(f"Mean (Average per Variable): {dist['mean']:.1f}")
        print(f"Std Dev: {dist['std_dev']:.1f}")
        print(f"\nPercentiles:")
        print(f"  25th: {dist['percentile_25']:.1f}")
        print(f"  75th: {dist['percentile_75']:.1f}")
        print(f"  90th: {dist['percentile_90']:.1f}")
        print(f"  95th: {dist['percentile_95']:.1f}")
        
        if 'concentration_90_percent' in dist:
            conc = dist['concentration_90_percent']
            print(f"\n📊 Concentration Analysis:")
            print(f"  {conc['variable_count']} variables ({conc['percentage_of_inputs']:.1f}% of inputs)")
            print(f"  contribute to 90% of all discovered variables")
        
        if 'ranges' in dist:
            ranges = dist['ranges']
            print(f"\n📈 Discovery Ranges:")
            print(f"  Zero discoveries: {ranges['zero']} variables")
            print(f"  1-10 discoveries: {ranges['1-10']} variables")
            print(f"  11-50 discoveries: {ranges['11-50']} variables")
            print(f"  51-100 discoveries: {ranges['51-100']} variables")
            print(f"  101-200 discoveries: {ranges['101-200']} variables")
            print(f"  200+ discoveries: {ranges['200+']} variables")
    
    # Output files
    print("\n" + "="*100)
    print("OUTPUT FILES:")
    print("="*100)
    print(f"📄 CSV (with batch column): {csv_path}")
    print(f"   Size: {Path(csv_path).stat().st_size / (1024*1024):.1f} MB")
    print(f"\n📊 JSON (detailed results): {json_path}")
    print(f"   Size: {Path(json_path).stat().st_size / 1024:.1f} KB")
    print("="*100)


# ============================================================================
# Main Driver
# ============================================================================

if __name__ == "__main__":
    print("="*100)
    print("K-HOP VARIABLE BATCHING - OPTIMIZED VERSION")
    print("="*100)
    print("Optimization: Only num_hops database queries per application")
    print("="*100)
    
    try:
        # 1. Setup configuration
        config = setup_configuration()
        print(f"\nConfiguration:")
        print(f"  Input CSV: {config['csv_path']}")
        print(f"  Number of Hops: {config['num_hops']}")
        print(f"  Case: {config['case']}")
        print(f"  Output Directory: {config['output_dir']}")
        print(f"  Applications: {len(config['app_to_db_map'])}")
        
        # 2. Load CSV data
        print("\n" + "="*100)
        print("Loading CSV Data...")
        print("="*100)
        original_rows, fieldnames, data_rows = load_csv_data(
            config['csv_path'],
            config['app_to_db_map']
        )
        print(f"✓ Loaded {len(data_rows)} variables from {len(original_rows)} rows")
        
        # 3. Group by application
        app_groups = group_by_application(data_rows)
        print(f"✓ Grouped into {len(app_groups)} applications")
        
        # 4. Process k-hop discovery (OPTIMIZED)
        all_results, variable_to_batch = process_k_hop_discovery_optimized(
            app_groups,
            config['num_hops']
        )
        
        # 5. Calculate statistics
        stats = calculate_statistics(all_results)
        
        # 6. Write outputs
        print("\n" + "="*100)
        print("Writing Output Files...")
        print("="*100)
        csv_path = write_output_csv(original_rows, fieldnames, variable_to_batch, config)
        print(f"✓ Records JSON written: {csv_path}")

        json_path = write_output_json(all_results, variable_to_batch, stats, config)
        print(f"✓ Analysis JSON written: {json_path}")

        # 7. Print summary
        print_summary(stats, csv_path, json_path)
        
    except FileNotFoundError as e:
        print(f"\n❌ Error: {e}")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
