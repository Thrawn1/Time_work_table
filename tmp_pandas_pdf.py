import pandas as pd
import pdfkit


options = {
    'page-size': 'A4',
    'orientation': 'Landscape',
    'encoding': "UTF-8",
    'custom-header': [
        ('Accept-Encoding', 'gzip')
    ]
}





#df = pd.read_excel("TEST_0000.xlsx")
#df = df.fillna('')
#print(df)
#df.to_html("file.html")
#pdfkit.from_file("test.html", "test_1.pdf",options=options,verbose=True)
pdfkit.from_file("test.html", "test_1.pdf",verbose=True,options=options)