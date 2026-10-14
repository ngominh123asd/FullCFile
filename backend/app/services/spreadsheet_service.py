"""
FileForge Backend - Spreadsheet Service
Uses openpyxl, pandas, and built-in csv for XLSX ↔ CSV ↔ JSON conversions
"""
import os
import io
import uuid
import json
import logging
from pathlib import Path
from typing import Optional, Tuple
import csv

logger = logging.getLogger(__name__)


class SpreadsheetService:
    """Spreadsheet conversion service with range selection & multi-sheet support."""

    async def convert(
        self,
        input_path: str,
        output_format: str,
        options: Optional[dict] = None,
    ) -> dict:
        """
        Convert spreadsheet to target format with optional range & sheet selection
        """
        if not os.path.exists(input_path):
            raise FileNotFoundError(f"Input file not found: {input_path}")

        options = options or {}
        input_ext = Path(input_path).suffix.lstrip(".").lower()

        output_dir = "/tmp/fileforge_outputs"
        os.makedirs(output_dir, exist_ok=True)

        output_filename = f"{uuid.uuid4()}.{output_format}"
        output_path = os.path.join(output_dir, output_filename)

        if input_ext == "csv" and output_format == "xlsx":
            await self._csv_to_xlsx(input_path, output_path, options)
        elif input_ext == "xlsx" and output_format == "csv":
            await self._xlsx_to_csv(input_path, output_path, options)
        elif input_ext == "xlsx" and output_format == "json":
            await self._xlsx_to_json(input_path, output_path, options)
        elif input_ext == "xlsx" and output_format == "xlsx":
            await self._xlsx_to_xlsx(input_path, output_path, options)
        elif input_ext == "csv" and output_format == "json":
            await self._csv_to_json(input_path, output_path, options)
        elif input_ext == "csv" and output_format == "csv":
            await self._csv_to_csv(input_path, output_path, options)
        elif input_ext == "json" and output_format == "xlsx":
            await self._json_to_xlsx(input_path, output_path, options)
        elif input_ext == "json" and output_format == "csv":
            await self._json_to_csv(input_path, output_path, options)
        elif input_ext == "ods" and output_format == "xlsx":
            await self._ods_to_xlsx(input_path, output_path, options)
        elif input_ext == "ods" and output_format == "csv":
            await self._ods_to_csv(input_path, output_path, options)
        elif input_ext == "ods" and output_format == "json":
            await self._ods_to_json(input_path, output_path, options)
        else:
            raise ValueError(f"Unsupported conversion: {input_ext} → {output_format}")

        if not os.path.exists(output_path):
            raise RuntimeError("Conversion produced no output")

        return {
            "output_path": output_path,
            "format": output_format,
            "size": os.path.getsize(output_path),
        }

    async def preview(
        self,
        input_path: str,
        max_rows: int = 50,
        options: Optional[dict] = None,
    ) -> dict:
        """Preview spreadsheet data with sheet metadata"""
        input_ext = Path(input_path).suffix.lstrip(".").lower()

        if input_ext == "xlsx":
            return await self._preview_xlsx(input_path, max_rows)
        elif input_ext == "csv":
            return await self._preview_csv(input_path, max_rows, options)
        elif input_ext == "json":
            return await self._preview_json(input_path, max_rows)
        return {"error": "Preview not supported for this format"}

    # ==================== Helpers ====================
    def _parse_row_col_boundaries(self, ws, options: Optional[dict] = None) -> Tuple[Optional[int], Optional[int], Optional[int], Optional[int]]:
        """Parse cell_range ('A1:H50') or discrete start/end row/col from options"""
        options = options or {}
        cell_range = options.get("cell_range")
        start_row = options.get("start_row")
        end_row = options.get("end_row")
        start_col = options.get("start_col")
        end_col = options.get("end_col")

        min_col, min_row, max_col, max_row = None, None, None, None

        if cell_range and ":" in str(cell_range):
            try:
                from openpyxl.utils.cell import range_boundaries
                min_col, min_row, max_col, max_row = range_boundaries(cell_range.strip().upper())
            except Exception as e:
                logger.warning(f"Failed to parse cell_range '{cell_range}': {e}")

        if min_row is None and start_row:
            try:
                min_row = int(start_row)
            except Exception:
                pass
        if max_row is None and end_row:
            try:
                max_row = int(end_row)
            except Exception:
                pass

        if min_col is None and start_col:
            try:
                from openpyxl.utils.cell import column_index_from_string
                min_col = column_index_from_string(str(start_col).strip().upper())
            except Exception:
                pass
        if max_col is None and end_col:
            try:
                from openpyxl.utils.cell import column_index_from_string
                max_col = column_index_from_string(str(end_col).strip().upper())
            except Exception:
                pass

        return min_row, max_row, min_col, max_col

    def _read_csv_text_and_delimiter(self, input_path: str, custom_delimiter: Optional[str] = None):
        content = None
        for enc in ("utf-8-sig", "utf-8", "windows-1258", "cp1252", "latin-1"):
            try:
                with open(input_path, "r", encoding=enc) as f:
                    content = f.read()
                break
            except Exception:
                continue

        if content is None:
            with open(input_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()

        delimiter = custom_delimiter
        if not delimiter:
            lines = [l for l in content.splitlines()[:25] if l.strip()]
            sample = "\n".join(lines)
            if sample:
                try:
                    dialect = csv.Sniffer().sniff(sample, delimiters=";,\t|")
                    delimiter = dialect.delimiter
                except Exception:
                    semi_count = sample.count(";")
                    comma_count = sample.count(",")
                    tab_count = sample.count("\t")
                    pipe_count = sample.count("|")
                    counts = {";": semi_count, ",": comma_count, "\t": tab_count, "|": pipe_count}
                    best = max(counts, key=counts.get)
                    delimiter = best if counts[best] > 0 else ","
            else:
                delimiter = ","

        return content, delimiter

    @staticmethod
    def _coerce_cell_value(val):
        """
        Coerce string or object to native numeric, boolean, or None type for Excel cells.
        If string is numeric (e.g. '123', '-45', '123.45', '0'), convert to int or float.
        Preserves strings with leading zeros that represent codes/identifiers (e.g. '0123', '007', '0987654321').
        """
        if val is None:
            return ""
        if isinstance(val, (int, float, bool)):
            return val
        if isinstance(val, str):
            val_strip = val.strip()
            if val_strip == "":
                return ""
            if val_strip.lower() == "true":
                return True
            if val_strip.lower() == "false":
                return False

            # Integer check: "123", "-45", "0"
            is_neg = val_strip.startswith("-")
            digits = val_strip[1:] if is_neg else val_strip
            if digits.isdigit():
                # Allow single "0" or numbers not starting with "0"
                if digits == "0" or not digits.startswith("0"):
                    try:
                        return int(val_strip)
                    except ValueError:
                        pass

            # Float check: "123.45", "-0.5", "0.05"
            if "." in val_strip:
                parts = val_strip.split(".")
                if len(parts) == 2:
                    int_part, dec_part = parts
                    int_digits = int_part[1:] if int_part.startswith("-") else int_part
                    if (int_digits.isdigit() or int_digits == "") and dec_part.isdigit():
                        if int_digits == "" or int_digits == "0" or not int_digits.startswith("0"):
                            try:
                                return float(val_strip)
                            except ValueError:
                                pass
        return val

    # ==================== XLSX ↔ CSV ====================
    async def _csv_to_xlsx(self, input_path: str, output_path: str, options: Optional[dict] = None):
        """Convert CSV to XLSX with robust delimiter & encoding detection and number coercion"""
        from openpyxl import Workbook

        options = options or {}
        in_delimiter = options.get("input_delimiter")
        content, delimiter = self._read_csv_text_and_delimiter(input_path, in_delimiter)

        wb = Workbook()
        ws = wb.active
        ws.title = options.get("sheet_name") or "Sheet1"

        reader = csv.reader(io.StringIO(content), delimiter=delimiter)
        for row in reader:
            if any(c is not None and str(c).strip() != "" for c in row):
                ws.append([self._coerce_cell_value(c) for c in row])

        wb.save(output_path)

    async def _csv_to_csv(self, input_path: str, output_path: str, options: Optional[dict] = None):
        """Filter or normalize CSV with UTF-8 BOM encoding and delimiter translation"""
        options = options or {}
        in_delimiter = options.get("input_delimiter")
        out_delimiter = options.get("delimiter", ",")
        content, src_delimiter = self._read_csv_text_and_delimiter(input_path, in_delimiter)

        reader = csv.reader(io.StringIO(content), delimiter=src_delimiter)
        with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f, delimiter=out_delimiter, quoting=csv.QUOTE_ALL)
            for row in reader:
                if any(c is not None and str(c).strip() != "" for c in row):
                    writer.writerow(row)

    async def _xlsx_to_csv(self, input_path: str, output_path: str, options: Optional[dict] = None):
        """Convert XLSX to CSV with range selection and UTF-8 BOM encoding"""
        from openpyxl import load_workbook

        options = options or {}
        delimiter = options.get("delimiter", ",")
        sheet_name = options.get("sheet_name")

        wb = load_workbook(input_path, data_only=True)
        if sheet_name and sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
        else:
            ws = wb.active

        min_row, max_row, min_col, max_col = self._parse_row_col_boundaries(ws, options)

        with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f, delimiter=delimiter, quoting=csv.QUOTE_ALL)
            for row in ws.iter_rows(min_row=min_row, max_row=max_row, min_col=min_col, max_col=max_col, values_only=True):
                if any(cell is not None for cell in row):
                    writer.writerow([str(c) if c is not None else "" for c in row])

    # ==================== XLSX ↔ XLSX (Range Crop / Sheet Extract) ====================
    async def _xlsx_to_xlsx(self, input_path: str, output_path: str, options: Optional[dict] = None):
        """Crop or filter XLSX by sheet and cell range"""
        from openpyxl import load_workbook, Workbook

        options = options or {}
        sheet_name = options.get("sheet_name")

        src_wb = load_workbook(input_path, data_only=True)
        if sheet_name and sheet_name in src_wb.sheetnames:
            src_ws = src_wb[sheet_name]
        else:
            src_ws = src_wb.active

        min_row, max_row, min_col, max_col = self._parse_row_col_boundaries(src_ws, options)

        out_wb = Workbook()
        out_ws = out_wb.active
        out_ws.title = src_ws.title

        for row in src_ws.iter_rows(min_row=min_row, max_row=max_row, min_col=min_col, max_col=max_col, values_only=True):
            if any(cell is not None for cell in row):
                out_ws.append([self._coerce_cell_value(c) if isinstance(c, str) else c for c in row])

        out_wb.save(output_path)

    # ==================== XLSX ↔ JSON ====================
    async def _xlsx_to_json(self, input_path: str, output_path: str, options: Optional[dict] = None):
        """Convert XLSX to JSON array of objects with range and sheet selection"""
        from openpyxl import load_workbook

        options = options or {}
        indent = options.get("indent", 2)
        sheet_name = options.get("sheet_name")

        wb = load_workbook(input_path, data_only=True)
        sheets_to_process = [sheet_name] if (sheet_name and sheet_name in wb.sheetnames) else wb.sheetnames

        result = {}
        for sname in sheets_to_process:
            ws = wb[sname]
            min_row, max_row, min_col, max_col = self._parse_row_col_boundaries(ws, options)
            rows = list(ws.iter_rows(min_row=min_row, max_row=max_row, min_col=min_col, max_col=max_col, values_only=True))
            if not rows:
                continue

            headers = [str(c) if c is not None else f"col_{i+1}" for i, c in enumerate(rows[0])]
            data = []
            for row in rows[1:]:
                if any(c is not None for c in row):
                    obj = {}
                    for h, c in zip(headers, row):
                        if c is None:
                            obj[h] = ""
                        elif isinstance(c, (int, float, bool)):
                            obj[h] = c
                        elif hasattr(c, "isoformat"):
                            obj[h] = c.isoformat()
                        else:
                            obj[h] = self._coerce_cell_value(c)
                    data.append(obj)
            result[sname] = data

        final_output = list(result.values())[0] if (len(result) == 1 and sheet_name) else result

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(final_output, f, indent=indent, ensure_ascii=False)

    async def _csv_to_json(self, input_path: str, output_path: str, options: Optional[dict] = None):
        """Convert CSV to JSON array with number coercion"""
        options = options or {}
        in_delimiter = options.get("input_delimiter")
        indent = options.get("indent", 2)
        content, delimiter = self._read_csv_text_and_delimiter(input_path, in_delimiter)

        reader = csv.DictReader(io.StringIO(content), delimiter=delimiter)
        data = [{k: self._coerce_cell_value(v) for k, v in row.items()} for row in reader]

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=indent, ensure_ascii=False)

    async def _json_to_xlsx(self, input_path: str, output_path: str, options: Optional[dict] = None):
        """Convert JSON to XLSX with automatic type coercion for numbers"""
        from openpyxl import Workbook

        with open(input_path, "r", encoding="utf-8-sig") as f:
            data = json.load(f)

        wb = Workbook()
        ws = wb.active
        ws.title = "Data"

        if isinstance(data, list):
            if data and isinstance(data[0], dict):
                headers = list(data[0].keys())
                ws.append(headers)
                for item in data:
                    ws.append([self._coerce_cell_value(item.get(h, "")) for h in headers])
            else:
                for row in data:
                    if isinstance(row, list):
                        ws.append([self._coerce_cell_value(c) for c in row])
                    else:
                        ws.append([self._coerce_cell_value(row)])
        elif isinstance(data, dict):
            for sheet_name, rows in data.items():
                if isinstance(rows, list) and rows:
                    if isinstance(rows[0], dict):
                        headers = list(rows[0].keys())
                        ws.append([f"--- {sheet_name} ---"] + headers)
                        for r in rows:
                            ws.append([self._coerce_cell_value(r.get(h, "")) for h in headers])
                    else:
                        ws.append([f"--- {sheet_name} ---"])
                        for r in rows:
                            if isinstance(r, list):
                                ws.append([self._coerce_cell_value(c) for c in r])
                            else:
                                ws.append([self._coerce_cell_value(r)])
                    ws.append([])

        wb.save(output_path)

    async def _json_to_csv(self, input_path: str, output_path: str, options: Optional[dict] = None):
        """Convert JSON array to CSV with UTF-8 BOM encoding for Excel"""
        with open(input_path, "r", encoding="utf-8-sig") as f:
            data = json.load(f)

        if not isinstance(data, list) or not data:
            raise ValueError("JSON must be array of objects for CSV conversion")

        if not isinstance(data[0], dict):
            raise ValueError("JSON array must contain objects")

        options = options or {}
        delimiter = options.get("delimiter", ",")

        headers = list(data[0].keys())
        with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=headers, delimiter=delimiter, quoting=csv.QUOTE_ALL)
            writer.writeheader()
            for row in data:
                writer.writerow(row)

    # ==================== ODS conversions ====================
    async def _ods_to_xlsx(self, input_path: str, output_path: str, options: Optional[dict] = None):
        import pandas as pd
        df = pd.read_excel(input_path, engine="odf")
        df.to_excel(output_path, index=False)

    async def _ods_to_csv(self, input_path: str, output_path: str, options: Optional[dict] = None):
        import pandas as pd
        options = options or {}
        delimiter = options.get("delimiter", ",")
        df = pd.read_excel(input_path, engine="odf")
        df.to_csv(output_path, index=False, sep=delimiter, encoding="utf-8-sig")

    async def _ods_to_json(self, input_path: str, output_path: str, options: Optional[dict] = None):
        import pandas as pd
        options = options or {}
        indent = options.get("indent", 2)
        df = pd.read_excel(input_path, engine="odf")
        records = df.to_dict(orient="records")
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(records, f, indent=indent, ensure_ascii=False)

    # ==================== Preview ====================
    async def _preview_xlsx(self, input_path: str, max_rows: int = 1000000) -> dict:
        from openpyxl import load_workbook

        wb = load_workbook(input_path, data_only=True)
        sheets = []
        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            data = []
            max_c = ws.max_column or 0
            max_r = ws.max_row or 0
            for i, row in enumerate(ws.iter_rows(values_only=True)):
                if i >= max_rows:
                    break
                data.append([str(c) if c is not None else "" for c in row])
            sheets.append({
                "name": sheet_name,
                "data": data,
                "total_rows": max_r,
                "total_cols": max_c,
            })
        return {
            "format": "xlsx",
            "sheets": sheets,
            "sheet_names": wb.sheetnames,
            "previewable": True,
        }

    async def _preview_csv(self, input_path: str, max_rows: int = 1000000, options: Optional[dict] = None) -> dict:
        options = options or {}
        in_delim = options.get("input_delimiter")
        content, delimiter = self._read_csv_text_and_delimiter(input_path, in_delim)

        data = []
        total_rows = 0
        reader = csv.reader(io.StringIO(content), delimiter=delimiter)
        for i, row in enumerate(reader):
            total_rows += 1
            if i >= max_rows:
                break
            if any(c is not None and str(c).strip() != "" for c in row):
                data.append(row)
        return {
            "format": "csv",
            "data": data,
            "delimiter": delimiter,
            "total_rows": total_rows,
            "total_cols": len(data[0]) if data else 0,
            "previewable": True,
        }

    async def _preview_json(self, input_path: str, max_rows: int = 1000000) -> dict:
        with open(input_path, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
        if isinstance(data, list):
            data = data[:max_rows]
        return {"format": "json", "data": data, "previewable": True}


# Singleton
spreadsheet_service = SpreadsheetService()
