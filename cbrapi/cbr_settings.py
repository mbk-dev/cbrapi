from suds.client import Client
from suds.xsd.doctor import Import, ImportDoctor


def make_cbr_client():
    global cbr_client
    imp = Import("http://www.w3.org/2001/XMLSchema")  # the schema to import
    imp.filter.add("http://web.cbr.ru/")  # the schema to import into
    d = ImportDoctor(imp)
    return Client(
        "http://www.cbr.ru/DailyInfoWebServ/DailyInfo.asmx?wsdl",
        doctor=d,
        retxml=True,
        headers={"User-Agent": "Mozilla"},
    )
