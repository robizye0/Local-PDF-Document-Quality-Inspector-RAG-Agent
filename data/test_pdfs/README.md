# Local PDF Test Set

These PDFs are downloaded fixtures for testing SpecCheck locally.

| File | Intended test | Validation |
|---|---|---|
| `01_lm358_datasheet.pdf` | `pcb-manufacturing` / technical datasheet | 68 pages, selectable text |
| `02_freshbooks_invoice.pdf` | `commercial-invoice` | 1 page, selectable text |
| `03_irs_w9_form.pdf` | generic form/document extraction | 6 pages, selectable text |
| `04_sample_scanned.pdf` | empty/image-only PDF rejection path | 3 pages, no text layer detected |
| `05_valid_invoice.pdf` | `commercial-invoice` positive path | 1 page, populated seller/buyer/items/totals/tax |
| `../uploads/test_spec.pdf` | `iso-compliance` | Existing project fixture |

## Sources

1. https://www.ti.com/lit/ds/symlink/lm358.pdf
2. https://www.freshbooks.com/media/2026/02/PDF-Invoice-Templates-US-Template-01.pdf
3. https://www.irs.gov/pub/irs-pdf/fw9.pdf
4. https://raw.githubusercontent.com/tinytoolkit-org/pdf-sample-files/4fd733c47ead5446b06372ab910cb78d1c7da55e/out/sample-scanned.pdf
