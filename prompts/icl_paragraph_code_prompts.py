"""This prompt was used for both the K-lines and paragraph code settings"""

Incontext_Examples = """Example 1
Input: "AG-COMBO-HFILL"
Output: [
    {
    "input": "AG-COMBO-HFILL",
    "short description": "Agar Combo Horizontal Fill",
    "long description": "A binary-long flag constant with value h'08', defined within the working-storage combo flags group, used to instruct the Agar GUI library to horizontally fill the available space when creating a combo widget via the AG_ComboNewS call; it is passed by value as a flag parameter to control the horizontal layout expansion behaviour of the combo box widget."
  }
  ]

Example 2
Input: "EIBTRNID"
Output: [
  {
    "input": "EIBTRNID",
    "short description": "Execute Interface Block Transaction Identifier",
    "long description": "A CICS Execute Interface Block field that holds the transaction identifier of the currently executing CICS transaction; read at program entry and copied into the working-storage field WS-TRANSID for logging and context alongside terminal and task identifiers, then evaluated throughout presentation-layer programs to branch business logic between inquiry and add operations, passed as the TRANSID operand in EXEC CICS RETURN statements to re-invoke the same transaction on screen return and clear flows, and used to set the appropriate screen heading title, enabling stateless pseudo-conversational processing across multiple health-domain entities including patients, visits, appointments, immunisations, and thresholds."
  }
]
"""



paragraph_code_prompt_v3_detailed = """You are a COBOL and software programming expert. For a given variable, generate the following (in English):
1. Short Description: Expand the variable name by replacing each abbreviation with its full form.
2. Long Description: A concise phrase using the expanded forms that captures the variable's purpose, business semantics, and interaction-driven implications, by considering all occurrences of the variable across the provided contextual excerpts, and remaining strictly faithful to the evidence.

COBOL-Specific Expansions (prioritize when applicable)
WS = Working-Storage
DFH = CICS
FD = File Description
RESP = Response Code
CA = Communication Area
EIB = Execute Interface Block

Output Format
[
  {
    "input": "provide input variable",
    "short description": "expanded form of the given input as a string in English",
    "long description": "concise phrase (strictly in English) aggregated from all variable occurrences, capturing its purpose, business semantics, and interaction-driven implications, while remaining faithful to the provided context"
  }
]

Context
The provided context is a collection of paragraphs or excerpts of code in which the variable appears.
Analyze all occurrences of the variable within these excerpts to infer its role, business logic, and interaction-driven implications.

Source Code Context:
{{SOURCE_CONTEXT}}

Reference Examples:
{{Incontext_Examples}}

Rules
1. Prefer COBOL-specific meanings when applicable.
2. Otherwise, use general programming interpretations.
3. Do not expand numerals.
4. Expand all acronyms in the short description (except numerals).
5. The long description must:
    a) reflect insights aggregated from all occurrences of the variable across the excerpts
    b) capture purpose, business semantics, and key interaction-driven implications 
    c) remain concise and non-redundant
    d) be strictly faithful to the code (no assumptions or hallucinations)
6. Treat the excerpts as the only source of truth; do not assume missing code or behavior
7. Ensure all of the output is strictly produced in English only.
8. Output strictly in the specified JSON format with no static_analyzertional text.

Input: {{TEST_VARIABLE}}""".replace("{{Incontext_Examples}}", Incontext_Examples)