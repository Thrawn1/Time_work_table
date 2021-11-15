# Use Aspose.Cells for Python via Java
import jpype
import asposecells
jpype.startJVM()
from asposecells.api import Workbook,SaveFormat,PdfSaveOptions,PdfCompliance,PageOrientationType


workbook = Workbook("TEST_0000.xlsx")
pdfOptions = PdfSaveOptions()
PageOrientation = PageOrientationType(0)
workbook.get

PdfSaveOptions
workbook.save("xlsx-to-pdf.pdf", SaveFormat.PDF)
