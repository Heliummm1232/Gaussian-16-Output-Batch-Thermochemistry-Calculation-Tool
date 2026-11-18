import os
import subprocess
import tkinter as tk
from tkinter import filedialog
from tkinter.scrolledtext import ScrolledText
import re
from rdkit import Chem
from rdkit.Chem import Draw, rdDepictor, rdDetermineBonds
from PIL import ImageTk

folder_path = ''
unit = ''
unit_json = {

    'Hartree':1.0,
    'Kcal':627.5059,
    'KJ':627.5059*4.184
}
setting_json = {}

with open('setting.ini','r',encoding='utf-8') as f:
    setting = f.readlines()
    for line in setting:
        key, sep, value = line.partition('=')
        setting_json[key.strip()] = value.strip()

def start_processing():
    try:
        global unit
        unit = selected_var.get()
        log_box.insert('end','单位是' + unit + '\n')
        ZPE = entry.get()
        if ZPE == '':
            ZPE = 0.961
        setting_json['sclZPE'] = float(ZPE)
        log_box.insert('end',f'ZPE为{ZPE}\n')
        log_box.insert('end','************************\n')
        if folder_path == '':
            log_box.insert('end','请先选择文件夹\n')
        else:
            processing_file(folder_path)
    except:
        log_box.insert('end','ZPE获取有误\n')
    
def get_path():
    try:
        global folder_path
        selected = filedialog.askdirectory(
        parent=window,
        title="请选择目标文件夹",
        mustexist=True)
        if not selected:
            log_box.insert('end','未选择文件夹\n')
            return
        folder_path = selected
        log_box.insert('end','文件路径为'+folder_path+'\n')
        log_box.insert('end','************************\n')
    except:
        log_box.insert('end','文件路径传入有误\n')
    
def processing_file(folder_path):
    coordiantion_lis = []
    for file_name in os.listdir(folder_path):
        file_path = os.path.join(folder_path, file_name)
        text = ''
        if str(file_name)[-3:] == 'out' or str(file_name)[-3:] == 'LOG':
            try:
                with open(file_path,'r',encoding='utf-8') as f:
                    text = f.read()
                    if is_complete(text):
                        if is_freq(text) and is_singlepoint(text) >= 1 and Standard_orientation(text):
                            coordiantion_lis.append(['','','',''])
                            coordiantion_lis[-1][0] = 'freq'
                            coordiantion_lis[-1][1] = file_path
                            coordiantion_lis[-1][2] = file_name
                            coordiantion_lis[-1][3] = search_coordination(text)
                            
                        elif (not is_freq(text)) and is_singlepoint(text) == 1 and Standard_orientation(text):
                            coordiantion_lis.append(['','','','','','',''])
                            coordiantion_lis[-1][0] = 'sp'
                            coordiantion_lis[-1][1] = file_path
                            coordiantion_lis[-1][2] = file_name
                            coordiantion_lis[-1][3] = search_coordination(text)
                            coordiantion_lis[-1][4] = search_sp(text)
                            coordiantion_lis[-1][5] = search_symbolic(text,file_name)
                            coordiantion_lis[-1][6] = search_charge(text)                       
            except:
                log_box.insert('end','读取'+file_name+'时出错\n')
    
    global patch_lis
    patch_lis = []

    for i in range(len(coordiantion_lis)-1):
        for j in range(i+1, len(coordiantion_lis)):
            if coordiantion_lis[i][3] != coordiantion_lis[j][3]:
                continue
            if coordiantion_lis[i][0] == 'freq' and coordiantion_lis[j][0] == 'sp':
                freq_record, sp_record = coordiantion_lis[i], coordiantion_lis[j]
            elif coordiantion_lis[i][0] == 'sp' and coordiantion_lis[j][0] == 'freq':
                freq_record, sp_record = coordiantion_lis[j], coordiantion_lis[i]
            else:
                continue
            # 0 freq 文件名  1 sp 文件名  2 freq 文件路径  3 能量
            # 4 symbolic z-matrix（XYZ 字符串）  5 电荷
            patch_lis.append([
                freq_record[2],
                sp_record[2],
                freq_record[1],
                sp_record[4],
                sp_record[5],
                sp_record[6],
            ])
            break

    for i in range(len(patch_lis)):
        setting_json['E'] = patch_lis[i][3]
        with open('setting.ini','w',encoding='utf-8') as f:
            for key,value in setting_json.items():
                f.write(f'{key} = {value}\n')
        patch_lis[i][3] = processing_shermo(patch_lis[i][2])
        log_box.insert('end',str(i+1)+'  '+patch_lis[i][0]+' '+ patch_lis[i][1]+' '+patch_lis[i][3]+'\n')

    log_box.insert('end','*************************\n')
    log_box.insert('end','选择基准物功能涉及多个分子能量相加时可能不适用\n')
    log_box.insert('end','现在可以自动绘制输出文件所对应的结构式图片\n')
    log_box.insert('end','*************************\n')

def is_complete(text):
    if 'Normal termination of Gaussian 16' in text:
        return True
    else:
        return False
    
def processing_shermo(path):
    try:
        result = subprocess.run(
            'Shermo.exe',
            input=path+'\n',
            capture_output=True,
            text=True,
            encoding='gbk',
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        text = result.stdout
        return search_gibbs(text)
    except:
        log_box.insert('end','shermo.exe run time error\n')
    
def is_freq(text):
    key = 'Thermal correction to Gibbs Free Energy='
    if key in text:
        return True

def is_singlepoint(text):
    count = 0
    key = 'SCF Done'
    count = text.count(key)
    return count

def Standard_orientation(text):
    key = 'Standard orientation'
    if key in text:
        return True
    
def search_coordination(text):

    pattern = (
    r"Standard orientation:.*?\n"
    r"[ \t]*-+[ \t]*\n"       # 第一条横线
    r".*?\n"                  # 表头
    r"[ \t]*-+[ \t]*\n"       # 第二条横线
    r"(.*?)"                  # 捕获坐标内容
    r"\n[ \t]*-+"             # 第三条横线
    )
    blocks = re.findall(pattern, text, flags=re.DOTALL)
    return blocks[-1]

def search_symbolic(text,file_name):
    value = re.compile(r'Symbolic Z-matrix:\s*\n\s*Charge\s*=\s*.*\d*\s*Multiplicity\s*=\s*\d*\s*\n(\s*\w+.*\n)+\s*\n')
    result = value.search(text)
    try:
        lines = result.group().splitlines()
        lines[0] = str(len(lines)-3)
        lines[1] = file_name
        return "\n".join(lines)
    
    except:
        log_box.insert('end',file_name+'  symbolic not found\n')
    
def search_charge(text):
    values = re.findall(r'Charge\s*=\s*(-?\d+)\s+Multiplicity', text)
    return int(values[-1]) if values else 0

def search_sp(text):
    values = re.findall(r"SCF Done:\s*E\([^)]*\)\s*=\s*([-+]?\d+(?:\.\d+)?(?:[EeDd][-+]?\d+)?)",text)
    return values[-1]

def search_gibbs(text):
    values = re.findall(r'Sum of electronic energy and thermal correction to G:\s*(-?\d+\.\d+)',text)
    gibbs = float(values[-1]) * unit_json[unit]
    return f"{gibbs:.8f}"

def calc_basis():
    try:
        basis_num = int(str(basis.get()).strip()) - 1
        if basis_num < 0 or basis_num >= len(patch_lis):
            raise ValueError('编号超出范围')
    except:
        log_box.insert('end','读取编号时出错\n')
        return

    try:
        for i in range(len(patch_lis)):
            log_box.insert('end',str(i+1)+'  '+patch_lis[i][0]+' '+ patch_lis[i][1]+' '+str(float(patch_lis[i][3])-float(patch_lis[basis_num][3]))+'\n')
        log_box.insert('end','********************\n')
    except:
        log_box.insert('end','输出时出错\n')

def mol_from_xyz(xyz, charge):
    xyz = (xyz or '').strip()
    mol = Chem.MolFromXYZBlock(xyz) if xyz else None
    if mol is None:
        return None
    try:
        rdDetermineBonds.DetermineBonds(mol, charge=charge)
    except Exception:
        try:
            rdDetermineBonds.DetermineConnectivity(mol)
            Chem.SanitizeMol(mol)
        except Exception:
            pass
    return mol

def show_structure():
    records = globals().get('patch_lis') or []
    if not records:
        log_box.insert('end','还没有可显示的结构，请先点击“运行”\n')
        return

    preview = tk.Toplevel(window)
    preview.title('结构式预览')
    preview.geometry('520x780')
    canvas = tk.Canvas(preview, bg='white')
    scrollbar = tk.Scrollbar(preview, orient='vertical', command=canvas.yview)
    canvas.configure(yscrollcommand=scrollbar.set)
    scrollbar.pack(side='right', fill='y')
    canvas.pack(side='left', fill='both', expand=True)
    preview.bind('<MouseWheel>', lambda e: canvas.yview_scroll(-1 if e.delta > 0 else 1, 'units'))
    inner = tk.Frame(canvas, bg='white')
    canvas.create_window((0, 0), window=inner, anchor='nw')
    inner.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))

    images = []
    for i, item in enumerate(records):
        tk.Label(inner, text=f'{i+1}. {item[1]}', bg='white', font=('Microsoft YaHei', 9)).pack(pady=(8, 0))
        mol = mol_from_xyz(item[4], item[5])
        if mol is None:
            tk.Label(inner, text='无法生成结构式', bg='white', fg='#b00020').pack(pady=4)
            continue
        try:
            mol = Chem.RemoveHs(mol)
        except Exception:
            pass
        try:
            mol.RemoveAllConformers()
            rdDepictor.Compute2DCoords(mol)
            photo = ImageTk.PhotoImage(Draw.MolToImage(mol, size=(460, 340)))
        except Exception:
            tk.Label(inner, text='绘制失败', bg='white', fg='#b00020').pack(pady=4)
            continue
        images.append(photo)
        tk.Label(inner, image=photo, bg='white').pack(pady=4)
    preview.images = images

window = tk.Tk()
window.title('Gaussian输出文件批处理脚本')
window.geometry('850x900')

tk.Button(window,text='选择文件夹',command=get_path).place(x=100,y=50)
tk.Button(window,text='运行',command=start_processing).place(x=200,y=50)
tk.Button(window,text='在右侧输入框中输入ZPE,默认为0.961').place(x=400,y=50)

entry = tk.Entry(window,width=20)
entry.place(x=630,y=55)

log_box = ScrolledText(window,height=50)
log_box.place(x=100,y=170)

selected_var = tk.StringVar(master=window, value='Hartree')
tk.OptionMenu(window,selected_var,'Hartree','Kcal','KJ').place(x=270,y=50,height=30,width=100)

tk.Button(window,text='右侧选择基准物编号 click me 空格分开',command=calc_basis).place(x=100,y=100)
tk.Button(window,text='show structure',command=show_structure).place(x=550,y=100)
basis = tk.Entry(window,width=20)
basis.place(x=350,y=105)


window.mainloop()