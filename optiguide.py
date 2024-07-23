# %% System Messages for AdPlacementOptimizer
WRITER_SYSTEM_MSG = """You are a chatbot to:
(1) write Python code to answer users' questions for an ad placement optimization project;
(2) explain solutions from a Python-based dynamic programming approach.

--- SOURCE CODE ---
{source_code}

--- DOC STR ---
{doc_str}
---

Here are some example questions and their answers and codes:
--- EXAMPLES ---
{example_qa}
---

The execution result of the original source code is below.
--- Original Result ---
{execution_result}

Note that your written code will be added to the lines with substring:
"# OPTIGUIDE *** CODE GOES HERE"
So, you don't need to write other code. Just write the code snippet in ```python ...``` block.
"""

SAFEGUARD_SYSTEM_MSG = """
Given the original source code:
{source_code}

Is the following code safe (not malicious code to break security
and privacy) to run?
Answer only one word.
If not safe, answer `DANGER`; else, answer `SAFE`.
"""

# %% Constant strings to match code lines in the source code for AdPlacementOptimizer
DATA_CODE_STR = "# OPTIGUIDE OVERRIDE INPUT VALUES CODE GOES HERE"
ALGORITHM_CODE_STR = "# OPTIGUIDE ALGORITHM CODE GOES HERE"


# %%
class OptiGuideAgent(AssistantAgent):
    """Modified OptiGuide Agent for AdPlacementOptimizer."""

    def __init__(self, name, source_code, doc_str="", example_qa="", debug_times=3, **kwargs):
        """
        Initialize the agent with the source code of AdPlacementOptimizer.
        """
        assert source_code.find(DATA_CODE_STR) >= 0, "DATA_CODE_STR not found."
        assert source_code.find(ALGORITHM_CODE_STR) >= 0, "ALGORITHM_CODE_STR not found."
        super().__init__(name, **kwargs)
        self._source_code = source_code
        self._doc_str = doc_str
        self._example_qa = example_qa
        self._origin_execution_result = _run_with_exec(source_code)
        self._writer = AssistantAgent("writer", llm_config=self.llm_config)
        self._safeguard = AssistantAgent("safeguard", llm_config=self.llm_config)
        self._debug_times_left = self.debug_times = debug_times
        self._success = False

    def generate_reply(
            self,
            messages: Optional[List[Dict]] = None,
            default_reply: Optional[Union[str, Dict]] = "",
            sender: Optional[Agent] = None,
    ) -> Union[str, Dict, None]:
        # Remove unused variables:
        # The message is already stored in self._oai_messages
        del messages, default_reply
        """Reply based on the conversation history."""
        if sender not in [self._writer, self._safeguard]:
            # Step 1: receive the message from the user
            user_chat_history = ("\nHere are the history of discussions:\n"
                                 f"{self._oai_messages[sender]}")
            writer_sys_msg = (WRITER_SYSTEM_MSG.format(
                source_code=self._source_code,
                doc_str=self._doc_str,
                example_qa=self._example_qa,
                execution_result=self._origin_execution_result,
            ) + user_chat_history)
            safeguard_sys_msg = SAFEGUARD_SYSTEM_MSG.format(
                source_code=self._source_code) + user_chat_history
            self._writer.update_system_message(writer_sys_msg)
            self._safeguard.update_system_message(safeguard_sys_msg)
            self._writer.reset()
            self._safeguard.reset()
            self._debug_times_left = self.debug_times
            self._success = False
            # Step 2-6: code, safeguard, and interpret
            self.initiate_chat(self._writer, message=CODE_PROMPT)
            if self._success:
                # step 7: receive interpret result
                reply = self.last_message(self._writer)["content"]
            else:
                reply = "Sorry. I cannot answer your question."
            # Finally, step 8: send reply to user
            return reply
        if sender == self._writer:
            # reply to writer
            return self._generate_reply_to_writer(sender)
        # no reply to safeguard

    def _generate_reply_to_writer(self, sender):
        if self._success:
            # no reply to writer
            return
        # Step 3: safeguard
        _, code = extract_code(self.last_message(sender)["content"])[0]
        self.initiate_chat(message=SAFEGUARD_PROMPT.format(code=code),
                           recipient=self._safeguard)
        safe_msg = self.last_message(self._safeguard)["content"]
        if safe_msg.find("DANGER") < 0:
            # Step 4 and 5: Run the code and obtain the results
            src_code = _insert_code(self._source_code, code)

            execution_rst = _run_with_exec(src_code)
            print(colored(str(execution_rst), "yellow"))
            if type(execution_rst) in [str, int, float]:
                # we successfully run the code and get the result
                self._success = True
                # Step 6: request to interpret results
                return INTERPRETER_PROMPT.format(execution_rst=execution_rst)
        else:
            # DANGER: If not safe, try to debug. Redo coding
            execution_rst = """
    Sorry, this new code is not safe to run. I would not allow you to execute it.
    Please try to find a new way (coding) to answer the question."""
        if self._debug_times_left > 0:
            # Try to debug and write code again (back to step 2)
            self._debug_times_left -= 1
            return DEBUG_PROMPT.format(error_type=type(execution_rst),
                                       error_message=str(execution_rst))


# %% Adapted Helper Functions for AdPlacementOptimizer

def _run_with_exec(src_code: str) -> Union[str, Exception]:
    locals_dict = {}
    locals_dict.update(globals())
    locals_dict.update(locals())

    timeout = Timeout(60, TimeoutError("Timeout exception in case of an infinite loop."))
    try:
        exec(src_code, locals_dict, locals_dict)
        optimizer = locals_dict['optimizer']
        # optimizer.print_optimal_strategy()
        return "Strategy executed. Check output."
    except Exception as e:
        return e
    finally:
        timeout.cancel()


def _replace(src_code: str, old_code: str, new_code: str) -> str:
    """
    Inserts new code into the source code by replacing a specified old
    code block.

    Args:
        src_code (str): The source code to modify.
        old_code (str): The code block to be replaced.
        new_code (str): The new code block to insert.

    Returns:
        str: The modified source code with the new code inserted.

    Raises:
        None

    Example:
        src_code = 'def hello_world():\n    print("Hello, world!")\n\n# Some
        other code here'
        old_code = 'print("Hello, world!")'
        new_code = 'print("Bonjour, monde!")\nprint("Hola, mundo!")'
        modified_code = _replace(src_code, old_code, new_code)
        print(modified_code)
        # Output:
        # def hello_world():
        #     print("Bonjour, monde!")
        #     print("Hola, mundo!")
        # Some other code here
    """
    pattern = r"( *){old_code}".format(old_code=old_code)
    head_spaces = re.search(pattern, src_code, flags=re.DOTALL).group(1)
    new_code = "\n".join([head_spaces + line for line in new_code.split("\n")])
    rst = re.sub(pattern, new_code, src_code)
    return rst


def _insert_code(src_code: str, new_lines: str) -> str:
    #     f = open('new.txt', 'w')
    #     f.write(new_lines)

    #     f.close()
    # Determine where to insert the code based on its content
    #     if "num_days" in new_lines:
    replaced_code = _replace(src_code, "# OPTIGUIDE OVERRIDE INPUT VALUES CODE GOES HERE", new_lines)

    return replaced_code
    # Add more conditions here for other variables if needed


#     return src_code  # Return the original source code if no relevant variable is found


# %% Updated Prompts for AdPlacementOptimizer

CODE_PROMPT = """
Answer Code:
"""

DEBUG_PROMPT = """
While running the code you suggested, I encountered an error:
--- ERROR MESSAGE ---
{error_message}

Please try to resolve this bug, and rewrite the code snippet.
--- NEW CODE ---
"""

SAFEGUARD_PROMPT = """
--- Code ---
{code}

--- One-Word Answer: SAFE or DANGER ---
"""

INTERPRETER_PROMPT = """Here are the execution results shown as tables: {execution_rst}

What insights do we get from the result based on the user question?

--- HUMAN READABLE ANSWER ---
"""