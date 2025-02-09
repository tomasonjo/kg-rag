import json
from datetime import datetime
from utils import chat, tool_choice
import ch05_tools

query_rewrite_prompt = """
    You are an expert in language and understanding semantic meaning.
    You read input from person and your job is to expand the input
    into stand alone atomic questions.

    You must return JSON using the template below.

    Example:
    Input: Who is Mick Jagger and how old is he?
    Output: 
    {
        "questions": [
            "Who is Mick Jagger?",
            "How old is Mick Jagger?"
        ]
    }
"""

def query_rewrite(input: str) -> list[str]:
        
        messages = [
            {"role": "system", "content": query_rewrite_prompt},
            {"role": "user", "content": f"The user question to rewrite: '{input}'"},
        ]
        config = {
            "response_format": {"type": "json_object"},
        }
        output = chat(messages, model = "gpt-4o", config=config, )
        try:
            return json.loads(output)["questions"]
        except json.JSONDecodeError:
            print("Error decoding JSON")
        return []

query_update_prompt = f"""
    You are an expert at updating questions to make the them ask for one thing only, more atomic, specific and easier to find the answer for.
    You do this by filling in missing information in the question, with the extra information provided to you in previous answers. 
    
    You respond with the updated question that has all information in it.
    Only edit the question if needed. If the original question already is atomic, specific and easy to answer, you keep the original.
    Do not ask for more information than the original question. Only rephrase the question to make it more complete.
    Today is {datetime.now()}
    
    JSON template to use:
    {{
        "question": "question1"
    }}
"""

def query_update(input: str, answers: list[any]) -> str: 
    messages = [
        {"role": "system", "content": query_update_prompt},
        *answers,
        {"role": "user", "content": f"The user question to optionally rewrite: '{input}'"},
    ]
    config = {"response_format": {"type": "json_object"}}
    output = chat(messages, model = "gpt-4o", config=config, )
    try:
        return json.loads(output)["question"]
    except json.JSONDecodeError:
        print("Error decoding JSON")
    return []

tool_picker_prompt = """
    Your job is to chose the right tool needed to respond to the user question. 
    The available tools are provided to you in the prompt.
    Make sure to pass the right and the complete arguments to the chosen tool.
"""

tools = {
    "movie_info_by_title": {
        "description": ch05_tools.movie_info_by_title_description,
        "function": ch05_tools.movie_info_by_title
    },
    "movies_info_by_actor": {
        "description": ch05_tools.movies_info_by_actor_description,
        "function": ch05_tools.movies_info_by_actor
    },
    "text2cypher": {
        "description": ch05_tools.text2cypher_description,
        "function": ch05_tools.text2cypher
    },
    "answer_given": {
        "description": ch05_tools.answer_given_description,
        "function": ch05_tools.answer_given
    }
}

def handle_tool_calls(tools: dict[str, any], llm_tool_calls: list[dict[str, any]]):
    output = []
    if llm_tool_calls:
        for tool_call in llm_tool_calls:
            function_to_call = tools[tool_call.function.name]["function"]
            function_args = json.loads(tool_call.function.arguments)
            res = function_to_call(**function_args)
            output.append(res)
    return output

def route_question(question: str, tools: dict[str, any], answers: list[dict[str, str]]):
    llm_tool_calls = tool_choice(
        [
            {
                "role": "system",
                "content": tool_picker_prompt,
            },
            *answers,
            {
                "role": "user",
                "content": f"The user question to find a tool to answer: '{question}'",
            },
        ],
        model = "gpt-4o",
        tools=[tool["description"] for tool in tools.values()],
    )
    return handle_tool_calls(tools, llm_tool_calls)

def handle_user_input(input: str, answers: list[dict[str, str]] = []):
    atomic_questions = query_rewrite(input)
    for question in atomic_questions:
        updated_question = question#query_update(question, answers)
        response  = route_question(updated_question, tools, answers)
        answers.append({"role": "assistant", "content": f"For the question: '{updated_question}', we have the answer: '{json.dumps(response)}'"})
    return answers

answer_critique_prompt = f"""
You specialize in evaluating whether a given response sufficiently addresses the original question or if there might be areas that could benefit from a little more clarification.

### Task:
- The user will provide a **question** and a corresponding **answers** from the chat history.
- Your job is to assess whether the answer adequately addresses the question.
- If you notice that the answer could be improved by adding some details or clarifications, feel free to suggest a few follow-up questions. These follow-up questions can be a bit more general or flexible, focusing on key areas that might need extra explanation.
- If the answer is already clear and sufficiently complete, simply return an empty list.

### Expected Output (JSON format):
```json
{{
    "questions": ["optional_follow_up_question_1", "optional_follow_up_question_2"]
}}
```

Today is `{datetime.now()}`.
"""

def critique_answers(question: str, answers: list[dict[str, str]]) -> list[str]:
    messages = [
        {
            "role": "system",
            "content": answer_critique_prompt,
        },
        *answers,
        {
            "role": "user",
            "content": f"Original user question: {question}. Does the answer include all the necessary details, or do we need to request further information?"
,
        },
    ]
    config = {"response_format": {"type": "json_object"}}
    output = chat(messages, model="gpt-4o", config=config)
    try:
        return json.loads(output)["questions"]
    except json.JSONDecodeError:
        print("Error decoding JSON")
    return []

main_prompt = """
    Your job is to help the user with their questions.
    You will receive user questions and information needed to answer the questions
    If the information is missing to answer part of or the whole question, you will say that the information 
    is missing. You will only use the information provided to you in the prompt to answer the questions.
    You are not allowed to make anything up or use external information.
"""

def get_answer(input: str):
    answers = handle_user_input(input)
    critique = critique_answers(input, answers)

    if critique:
        answers = handle_user_input(" ".join(critique), answers)

    llm_response = chat(
        [
            {"role": "system", "content": main_prompt},
            *answers,
            {"role": "user", "content": f"The user question to answer: {input}"},
        ],
        model="gpt-4o",
    )

    return llm_response, answers