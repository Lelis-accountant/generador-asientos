# 📥 Generador de Asientos Contables desde Extracto PDF

Esta aplicación en **Streamlit** procesa extractos bancarios en PDF del Banco Galicia
y genera automáticamente:

- 📄 Una planilla con los **movimientos clasificados**
- 🧾 El **asiento contable balanceado**
- 📊 Un detalle adicional de **pagos a proveedores**

## 🚀 Cómo usar

1. Subí un extracto PDF (descargado de Banco Galicia).
2. La app lo procesa y clasifica cada movimiento según reglas predefinidas.
3. Descargá el archivo Excel con tres pestañas:
   - **Movimientos Clasificados**
   - **Asiento Contable**
   - **Detalle Proveedores** (si aplica)

## 🔧 Instalación local

```bash
pip install -r requirements.txt
streamlit run app(2).py
```

## 🌐 Deploy en Streamlit Cloud

Subí estos archivos a tu repositorio de GitHub:

- `app(2).py`
- `requirements.txt`
- `README.md`

Y luego conectá tu repo a [streamlit.io](https://streamlit.io/).

---

✍️ Adaptado para extractos PDF **Banco Galicia**.  
Se pueden agregar más reglas de clasificación editando el diccionario `cuentas` en `app(2).py`.
