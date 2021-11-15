import jpype
jpype.startJVM()
from asposecells.api import Workbook, FileFormatType, PdfSaveOptions

def generation_pdf_file(id:int,name_excel_file:str):
    workbook = Workbook("TEST_0000.xlsx")
    saveOptions = PdfSaveOptions()
    saveOptions.setOnePagePerSheet(True)
    workbook.save("example.pdf", saveOptions)
    jpype.shutdownJVM()