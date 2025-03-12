import os
import uuid
from datetime import datetime, timezone
from fpdf import FPDF


# Constants
LOCATION = os.environ.get("LOCATION", "San Salvador")
BASE_BANK = os.environ.get("BASE_BANK", "BaseBank")
DEFAULT_OUTPUT_PATH = "/tmp"  # Used for Lambda ephemeral storage


class PDF(FPDF):
    def header(self):
        self.set_font("Arial", "B", 12)
        self.cell(0, 10, "DEMO EDUCATIVA", border=False, ln=True, align="R")
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font("Arial", "I", 8)
        self.cell(0, 10, f"Page {self.page_no()}", align="C")


def generate_document_pdf(
    title,
    project_details,
    document_key,
    amount_key,
    amount_value,
    details_1,
    valor_en_letras,
    date,
    nombre_emisor,
    final_note,
    document_value=None,
    output_path=DEFAULT_OUTPUT_PATH,
):
    """
    Function to generate a PDF document with the given structure.

    Args:
        title (str): Title of the document.
        project_details (str): Description of the project details.
        document_key (str): Key for the document field.
        document_value (str): Value for the document field.
        amount_key (str): Key for the amount field.
        amount_value (str): Value for the amount field.
        details_1 (str): Additional details.
        valor_en_letras (str): Amount in words.
        date (str): Date to include in the document.
        nombre_emisor (str): Name of the issuer.
        final_note (str): Final note to include in the document.
        output_path (str): Path to save the generated PDF.

    Returns:
        str: Path to the generated PDF file.
    """
    # Create a PDF instance
    pdf = PDF()
    pdf.set_auto_page_break(auto=True, margin=15)

    # Add a new page
    pdf.add_page()

    # Add image
    image_path = os.path.join(os.path.dirname(__file__), BASE_BANK, "bank_logo.png")
    if image_path and os.path.exists(image_path):
        pdf.image(image_path, x=10, y=10, w=20)

    if document_value is None:
        document_value = str(uuid.uuid4())

    # Add title and project details
    pdf.set_xy(70, 10)
    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 10, title, ln=True)
    pdf.set_font("Arial", "", 12)
    pdf.cell(0, 10, "", ln=True)
    pdf.cell(0, 10, project_details, ln=True)
    pdf.ln(15)

    # Add document and amount details
    pdf.set_font("Arial", "", 10)
    pdf.cell(50, 10, f"{document_key}:", border=0)
    pdf.cell(0, 10, document_value, ln=True, border=0)
    pdf.cell(50, 10, f"{amount_key}:", border=0)
    pdf.cell(0, 10, amount_value, ln=True, border=0)
    pdf.ln(10)

    # Add additional details
    pdf.cell(0, 10, details_1, ln=True)
    pdf.cell(50, 10, "Cantidad:", border=0)
    pdf.cell(0, 10, valor_en_letras, ln=True)
    pdf.cell(50, 10, "USD:", border=0)
    pdf.cell(0, 10, date, ln=True)
    pdf.cell(50, 10, "A favor de:", border=0)
    pdf.cell(0, 10, nombre_emisor, ln=True)
    pdf.ln(10)

    # ISO 8601 timestamp for ordering
    timestamp = datetime.now(timezone.utc).isoformat()
    pdf.cell(50, 10, "Fecha Generación Documento:", border=0)
    pdf.cell(0, 10, timestamp, ln=True)
    pdf.ln(10)

    # Add final note
    pdf.multi_cell(0, 10, final_note)
    pdf.ln(10)

    # Add signature image
    signature_image_path = os.path.join(
        os.path.dirname(__file__), BASE_BANK, "signature.png"
    )
    if signature_image_path and os.path.exists(signature_image_path):
        pdf.cell(0, 10, "Administración:", ln=True)
        pdf.image(signature_image_path, x=10, y=pdf.get_y(), w=50)

    # Save the PDF
    os.makedirs(output_path, exist_ok=True)
    output_file = os.path.join(output_path, "bank_certificate.pdf")
    pdf.output(output_file)

    return output_file


# Example usage
if __name__ == "__main__":
    pdf_path = generate_document_pdf(
        title="DemoBank",
        project_details="Proyecto No: 980",
        document_key="No.",
        document_value="1354132",
        amount_key="POR:",
        amount_value="$ 126.29",
        details_1="QUEDAN en nuestro poder para revisión las Factura(s)/Recibido(s) No.: 4209,4215",
        valor_en_letras="Ciento veintiseis 28/100",
        date="2025-03-11",
        nombre_emisor="Demo Emisor SAS",
        final_note="This document is issued for DEMO purposes only.",
        output_path="./temp",
    )
    print(f"PDF generated at: {pdf_path}")
