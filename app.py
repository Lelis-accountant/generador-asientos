
import streamlit as st
import fitz  # PyMuPDF
import pandas as pd
import re
import unicodedata
from io import BytesIO

st.set_page_config(page_title="Generador de Asientos Contables", layout="centered")
st.title("📥 Generador de Asientos Contables desde Extracto PDF")

# ----------------- Diccionario de cuentas -----------------
cuentas = {
    "Comisiones y Gastos Bancarios": {"tipo": "DEBE", "claves": [
        r"COMISION SERVICIO DE CUENTA",
        r"COMISION DEPOSITOS EN EFECTIVO",
        r"COM\. GESTION TRANSF\.FDOS ENTRE BCOS",
        r"\bIVA\b",
        r"COM DEP EFVO BILL BAJA DENOMINACION",
        r"SERVICIO TERMINAL PAYWAY"
    ]},
    "Anticipo imp. Deb. Cred.Bancario Ley 25413": {"tipo": "DEBE", "claves": [
        r"IMP\. DEB\. LEY 25413 GRAL",
        r"IMP\. CRE\. LEY 25413"
    ]},
    "Devolución imp. Deb. Cred.Bancario Ley 25413": {"tipo": "HABER", "claves": [
        r"DEV\.IMP\.DEB\.LEY 25413-ALIC\.GENERAL"
    ]},
    "Proveedores": {"tipo": "DEBE", "claves": [
        r"PERCEP\. IVA",
        r"IMP\. ING\. BRUTOS",
        r"TRF INMED PROVEED",
        r"PAGO DE SERVICIOS",
        r"TRANSF\. A TERCEROS"
    ]},
    "Sueldos a pagar": {"tipo": "DEBE", "claves": [
        r"SERVICIO ACREDITAMIENTO DE HABERES"
    ]},
    "PAGOS AFIP": {"tipo": "DEBE", "claves": [
        r"TRANSF\. AFIP",
        r"DEB\. AUTOM\. DE SERV\. AFIP"
    ]},
    "Deudores x ventas": {"tipo": "HABER", "claves": [
        r"ACREDITAMIENTO PRISMA-COMERCIOS",
        r"DEPOSITO EN EFECTIVO",
        r"SERVICIO PAGO A PROVEEDORES",
        r"TRANSFERENCIA PEI",
        r"TRANSFERENCIAS CASH PROVEEDORES"
    ]},
    "PAGOS Ingresos Brutos AGIP": {"tipo": "DEBE", "claves": [
        r"DEB\. AUTOM\. DE SERV\. RENTAS\.CDAD\.BSAS"
    ]},
    "Inversiones Banco": {"tipo": "HABER", "claves": [
        r"RESCATE FIMA",
        r"SUSCRIPCION FIMA"
    ]},
    "Juicios Afip": {"tipo": "HABER", "claves": [
        r"DEVOLUCION ORDEN JUDICIAL"
    ]},
    "Sircreb": {"tipo": "DEBE", "claves": [
        r"ING\. BRUTOS S/ CRED REG\.RECAU\.SIRCREB"
    ]},
    "Intereses Bancarios": {"tipo": "DEBE", "claves": [
        r"INTERESES SOBRE SALDOS DEUDORES"
    ]},
    "Impuesto de Sellos": {"tipo": "DEBE", "claves": [
        r"IMPUESTO DE SELLOS"
    ]},
    "Tarjetas de Crédito": {"tipo": "DEBE", "claves": [
        r"PAGO VISA EMPRESA",
        r"PAGO MASTERCARD EMPRESA"
    ]},
    "Transferencias propias": {"tipo": "HABER", "claves": [
        r"TRANSFERENCIA DE CUENTA PROPIA"
    ]},
}

# ----------------- Utilidades -----------------
importe_re = re.compile(r"^\(?-?\d{1,3}(\.\d{3})*(\s?\d{3})*,\d{2}\)?$")
fecha_re = re.compile(r"^\d{2}/\d{2}/\d{2}$")
fecha_en_linea_re = re.compile(r"^(\d{2}/\d{2}/\d{2})\s+(.*)$")

def normalize_text(s: str) -> str:
    if not isinstance(s, str):
        return ""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = re.sub(r"\s+", " ", s).strip()
    return s.upper()

def to_float(val: str) -> float:
    if not val:
        return 0.0
    v = val.replace(".", "").replace(" ", "").replace(",", ".")
    v = v.replace("(", "-").replace(")", "")
    try:
        return float(v)
    except:
        return 0.0

def corregir_importe(row) -> float:
    debe = abs(row.get("Débito", 0.0) or 0.0)
    haber = abs(row.get("Crédito", 0.0) or 0.0)
    if row.get("Tipo") == "DEBE":
        return debe if debe != 0 else haber
    elif row.get("Tipo") == "HABER":
        return haber if haber != 0 else debe
    return 0.0

def match_cuenta(desc_norm: str):
    for cuenta, info in cuentas.items():
        for patron in info["claves"]:
            if re.search(patron, desc_norm):
                return cuenta, info["tipo"]
    return None, None

# ----------------- Parser -----------------
def leer_lineas_pdf(file):
    doc = fitz.open(stream=file.read(), filetype="pdf")
    try:
        lines = []
        for page in doc:
            lines.extend(page.get_text("text").split("\\n"))
        return [ln for ln in lines if ln.strip()]
    finally:
        doc.close()

def procesar_pdf(file):
    raw_lines = leer_lineas_pdf(file)
    lines = [(ln, normalize_text(ln)) for ln in raw_lines]

    movimientos = []
    i = 0
    n = len(lines)

    while i < n:
        original, norm = lines[i]

        # fecha sola o fecha + descripción
        fecha = None
        descripcion = ""
        if re.match(fecha_re, norm):
            fecha = original
            j = i + 1
        else:
            m = re.match(fecha_en_linea_re, original)
            if m:
                fecha = m.group(1)
                descripcion = m.group(2).strip()
                j = i + 1
            else:
                i += 1
                continue

        # descripción multilínea
        descripcion_parts = []
        if descripcion:
            descripcion_parts.append(descripcion)
        while j < n and not importe_re.match(lines[j][0].strip()):
            descripcion_parts.append(lines[j][0])
            j += 1

        valores = []
        while j < n and importe_re.match(lines[j][0].strip()):
            valores.append(lines[j][0])
            j += 1

        saldo = credito = debito = ""
        if len(valores) == 2:
            credito, saldo = valores
        elif len(valores) >= 3:
            credito, debito, saldo = valores[-3:]

        desc = " ".join(descripcion_parts).strip()
        cuenta, tipo = match_cuenta(normalize_text(desc))

        movimientos.append({
            "Fecha": fecha,
            "Descripción": desc,
            "Crédito": to_float(credito),
            "Débito": to_float(debito),
            "Saldo": to_float(saldo),
            "Cuenta Contable": cuenta,
            "Tipo": tipo
        })

        i = j

    df = pd.DataFrame(movimientos)
    if df.empty:
        return BytesIO()

    df["Importe"] = df.apply(corregir_importe, axis=1)

    asiento = (
        df[df["Cuenta Contable"].notna()]
        .groupby(["Cuenta Contable", "Tipo"], as_index=False)["Importe"]
        .sum()
    )

    debe_total = asiento.loc[asiento["Tipo"]=="DEBE", "Importe"].sum()
    haber_total = asiento.loc[asiento["Tipo"]=="HABER", "Importe"].sum()
    diferencia = round(debe_total - haber_total, 2)
    if abs(diferencia) > 0.01:
        asiento.loc[len(asiento.index)] = {
            "Cuenta Contable": "Banco",
            "Tipo": "HABER" if diferencia > 0 else "DEBE",
            "Importe": abs(diferencia)
        }

    detalle_proveedores = df[
        df["Descripción"].str.contains(r"TRF INMED PROVEED|PAGO DE SERVICIOS|TRANSF\. A TERCEROS", case=False, regex=True, na=False)
    ].copy()
    if not detalle_proveedores.empty:
        detalle_proveedores["Débito"] = detalle_proveedores["Débito"].abs()

    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Movimientos Clasificados", index=False)
        asiento.to_excel(writer, sheet_name="Asiento Contable", index=False)
        if not detalle_proveedores.empty:
            detalle_proveedores.to_excel(writer, sheet_name="Detalle Proveedores", index=False)
    output.seek(0)
    return output

# ----------------- UI -----------------
uploaded_file = st.file_uploader("Subí tu archivo PDF de extracto bancario", type="pdf")

if uploaded_file is not None:
    st.success("Archivo cargado correctamente. Procesando…")
    excel_output = procesar_pdf(uploaded_file)
    if excel_output.getbuffer().nbytes == 0:
        st.error("No se detectaron movimientos.")
    else:
        st.download_button("📥 Descargar Asiento Contable (.xlsx)", data=excel_output, file_name="asiento_contable.xlsx")
