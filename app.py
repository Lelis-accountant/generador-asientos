
import streamlit as st
import fitz  # PyMuPDF
import pandas as pd
import re
from io import BytesIO

st.set_page_config(page_title="Generador de Asientos Contables", layout="centered")
st.title("📥 Generador de Asientos Contables desde Extracto PDF")

cuentas = {
    "Comisiones y Gastos Bancarios": {"tipo": "DEBE", "claves": ["COMISION SERVICIO DE CUENTA", "COMISION DEPOSITOS EN EFECTIVO", "COM. GESTION TRANSF.FDOS ENTRE BCOS", "IVA", "COM DEP EFVO BILL BAJA DENOMINACION", "SERVICIO TERMINAL PAYWAY"]},
    "Anticipo imp. Deb. Cred.Bancario Ley 25413": {"tipo": "DEBE", "claves": ["IMP. DEB. LEY 25413 GRAL", "IMP. CRE. LEY 25413", "DEV.IMP.DEB.LEY 25413-ALIC.GENERAL"]},
    "Proveedores": {"tipo": "DEBE", "claves": ["PERCEP. IVA", "IMP. ING. BRUTOS", "TRF INMED PROVEED", "PAGO DE SERVICIOS"]},
    "Sueldos a pagar": {"tipo": "DEBE", "claves": ["SERVICIO ACREDITAMIENTO DE HABERES"]},
    "PAGOS AFIP": {"tipo": "DEBE", "claves": ["TRANSF. AFIP", "DEB. AUTOM. DE SERV. AFIP"]},
    "Deudores x ventas": {"tipo": "HABER", "claves": ["ACREDITAMIENTO PRISMA-COMERCIOS", "DEPOSITO EN EFECTIVO", "SERVICIO PAGO A PROVEEDORES"]},
    "PAGOS Ingresos Brutos AGIP": {"tipo": "DEBE", "claves": ["DEB. AUTOM. DE SERV. RENTAS.CDAD.BSAS"]},
    "Inversiones Banco": {"tipo": "DEBE", "claves": ["RESCATE FIMA FIMA PREMIUM CLASE B", "SUSCRIPCION FIMA FIMA AHORRO PLUS CLA", "RESCATE FIMA FIMA RENTA EN PESOS"]},
    "Juicios Afip": {"tipo": "HABER", "claves": ["DEVOLUCION ORDEN JUDICIAL"]},
}

def to_float(val):
    try: return float(val.replace('.', '').replace(',', '.'))
    except: return 0.0

def corregir_importe(row):
    if row["Tipo"] == "DEBE":
        return abs(row["Débito"]) if row["Débito"] != 0 else abs(row["Crédito"])
    elif row["Tipo"] == "HABER":
        return row["Crédito"]
    return 0.0

def clasificar_cuenta(desc):
    for cuenta, info in cuentas.items():
        if any(k in desc for k in info["claves"]):
            return cuenta, info["tipo"]
    return None, None

def procesar_pdf(file):
    doc = fitz.open(stream=file.read(), filetype="pdf")
    lines = []
    for page in doc:
        lines.extend(page.get_text().split("\n"))

    movimientos = []
    for i in range(len(lines)):
        if re.match(r"\d{2}/\d{2}/\d{2}", lines[i]):
            fecha = lines[i]
            j = i + 1
            descripcion = ""
            while j < len(lines) and not re.match(r"^-?\d{1,3}(\.\d{3})*,\d{2}$", lines[j]):
                descripcion += lines[j] + " "
                j += 1
            valores = []
            while j < len(lines) and re.match(r"^-?\d{1,3}(\.\d{3})*,\d{2}$", lines[j]):
                valores.append(lines[j])
                j += 1
            saldo = valores[-1] if valores else ""
            credito, debito = "", ""
            if len(valores) == 2: credito, saldo = valores
            elif len(valores) == 3: credito, debito, saldo = valores
            cuenta, tipo = clasificar_cuenta(descripcion.strip())
            movimientos.append({
                "Fecha": fecha,
                "Descripción": descripcion.strip(),
                "Crédito": to_float(credito),
                "Débito": to_float(debito),
                "Saldo": to_float(saldo),
                "Cuenta Contable": cuenta,
                "Tipo": tipo
            })

    df = pd.DataFrame(movimientos)
    df["Importe"] = df.apply(corregir_importe, axis=1)
    df = df[~df["Descripción"].str.contains("Período de movimientos", case=False)]

    asiento = df[df["Cuenta Contable"].notnull()].groupby(["Cuenta Contable", "Tipo"]).agg({"Importe": "sum"}).reset_index()
    debe_total = asiento[asiento["Tipo"] == "DEBE"]["Importe"].sum()
    haber_total = asiento[asiento["Tipo"] == "HABER"]["Importe"].sum()
    diferencia = round(debe_total - haber_total, 2)
    if diferencia != 0:
        asiento.loc[len(asiento.index)] = {"Cuenta Contable": "Banco", "Tipo": "HABER" if diferencia > 0 else "DEBE", "Importe": abs(diferencia)}

    detalle_proveedores = df[df["Descripción"].str.contains("TRF INMED PROVEED|PAGO DE SERVICIOS", case=False)].copy()
    detalle_proveedores["Débito"] = detalle_proveedores["Débito"].abs()

    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Movimientos Clasificados", index=False)
        asiento.to_excel(writer, sheet_name="Asiento Contable", index=False)
        detalle_proveedores.to_excel(writer, sheet_name="Detalle Proveedores", index=False)
    output.seek(0)
    return output

uploaded_file = st.file_uploader("Subí tu archivo PDF de extracto bancario", type="pdf")

if uploaded_file is not None:
    st.success("Archivo cargado correctamente. Procesando...")
    excel_output = procesar_pdf(uploaded_file)
    st.download_button("📥 Descargar Asiento Contable (.xlsx)", data=excel_output, file_name="asiento_contable.xlsx")
