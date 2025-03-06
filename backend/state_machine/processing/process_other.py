# Own imports
from state_machine.base_step_function import BaseStepFunction
from common.logger import custom_logger


logger = custom_logger()


class ProcessOther(BaseStepFunction):
    """
    This class contains methods that serve as the "process other" for the State Machine.
    """

    def __init__(self, event):
        super().__init__(event, logger=logger)

    def process_other(self):
        """
        Method to execute the step to 'process_other' workflow.
        """

        self.logger.info("Starting process_other step")

        message = "Process Other not implemented yet."
        self.logger.info(message)

        self.event["response_process_other"] = message

        return self.event
