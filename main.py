from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import pdfplumber, re, tempfile, os

app = FastAPI()

app.add_middleware(CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"])

def parse_num(s):
    return float(s.replace('.', '').replace(',', '.'))

def extrair_nums(parts):
    nums = []
    for p in reversed(parts):
        try:
            nums.insert(0, parse_num(p))
            if len(nums) == 7: break
        except: break
    if len(nums) < 7: return None, None
    return ' '.join(parts[:len(parts)-7]).strip(), nums

def parsear_pdf(caminho):
    produtos, fornecedor, categoria, pending = [], '', '', None
    SKIP = ["D'CASA", 'Relação', 'Id:', 'Estoque:', 'Data:', 'Página:']
    with pdfplumber.open(caminho) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text: continue
            for line in text.split('\n'):
                line = line.strip()
                if not line: continue
                if 'Fornecedor:' in line:
                    m = re.search(r'Fornecedor:(.+?)(?:\s{2,}|Categoria:|$)', line)
                    if m: fornecedor = m.group(1).strip()
                    c = re.search(r'Categoria:\s*(.+)', line)
                    if c: categoria = c.group(1).strip()
                    pending = None; continue
                if any(s in line for s in SKIP): pending = None; continue
                m = re.match(r'^(\d{3,6})(.*)', line)
                if m:
                    id_p, resto = m.group(1), m.group(2).strip()
                    desc, nums = extrair_nums(resto.split())
                    if nums:
                        produtos.append({'id_produto': id_p, 'descricao': desc,
                            'fornecedor': fornecedor, 'categoria': categoria,
                            'estoque_qtd': nums[0], 'preco_custo': nums[1],
                            'icms_percentual': nums[2], 'ipi_percentual': nums[3],
                            'frete_valor': nums[4], 'desconto_percentual': nums[5],
                            'preco_liquido': nums[6]}); pending = None
                    else: pending = {'id': id_p, 'acc': resto}
                elif pending:
                    acc = pending['acc'] + ' ' + line
                    desc, nums = extrair_nums(acc.split())
                    if nums:
                        produtos.append({'id_produto': pending['id'], 'descricao': desc,
                            'fornecedor': fornecedor, 'categoria': categoria,
                            'estoque_qtd': nums[0], 'preco_custo': nums[1],
                            'icms_percentual': nums[2], 'ipi_percentual': nums[3],
                            'frete_valor': nums[4], 'desconto_percentual': nums[5],
                            'preco_liquido': nums[6]}); pending = None
                    else: pending['acc'] = acc
    return produtos

@app.get("/")
def health():
    return {"status": "ok", "service": "ERP PDF Parser"}

@app.post("/parse-pdf")
async def parse_pdf(file: UploadFile = File(...)):
    with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name
    try:
        produtos = parsear_pdf(tmp_path)
        return {"total": len(produtos), "produtos": produtos}
    finally:
        os.unlink(tmp_path)
