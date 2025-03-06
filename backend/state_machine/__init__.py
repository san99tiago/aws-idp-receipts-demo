################################################################################
# !!! IMPORTANT !!!
#  This __init__.py allows to load the relevant classes from the State Machine.
#  By importing this file, we leverage "globals" and "getattr" to dynamically
#  execute the Step Function's inner Lambda Functions classes.
################################################################################

# Validation (Prepare)
from state_machine.utils.validate_input import ValidateInput  # noqa

# Processing (Extract, Transform)
from state_machine.processing.process_image import ProcessImage  # noqa
from state_machine.processing.process_pdf import ProcessPDF  # noqa
from state_machine.processing.process_other import ProcessOther  # noqa

# Saving (Load)
from state_machine.save.save_data import SaveData  # noqa

# Utils
from state_machine.utils.success import Success  # noqa
from state_machine.utils.failure import Failure  # noqa
