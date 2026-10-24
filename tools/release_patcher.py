"""Standalone v0.855 installer. Bundles a delta; the user supplies the game."""
from __future__ import annotations
import argparse,hashlib,json,os,queue,re,shutil,struct,subprocess,sys,tempfile,threading,zlib
from pathlib import Path

VERSION='0.855'
NAME='Space Adventure Cobra KR v0.855'
RES=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parents[1]/'release/v0.855/patcher-assets'))

def sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def run(command):
    r=subprocess.run([str(x) for x in command],capture_output=True,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    if r.returncode:
        raise RuntimeError((r.stdout+r.stderr).decode('utf-8','replace')[-1800:] or 'CHD 도구 실행 실패')
    return (r.stdout+r.stderr).decode('utf-8','replace')

def assets():
    m=json.loads((RES/'manifest.json').read_text(encoding='utf-8'))
    for name,digest in m['assets'].items():
        if sha(RES/name)!=digest:raise ValueError('패처 구성 파일이 손상되었습니다. 다시 내려받아 주세요.')
    return m

def source_bin(source,work,log):
    suffix=source.suffix.lower()
    if suffix=='.chd':
        log('원본 CHD를 읽는 중…')
        run([RES/'chdman.exe','extractcd','-i',source,'-o',work/'original.cue','-ob',work/'original.bin'])
        return work/'original.bin'
    if suffix=='.cue':
        raw=source.read_bytes()
        try:text=raw.decode('utf-8-sig')
        except UnicodeDecodeError:text=raw.decode('cp932')
        names=re.findall(r'^\s*FILE\s+"([^"]+)"\s+BINARY\s*$',text,re.M|re.I)
        if len(names)!=1:raise ValueError('단일 BIN을 사용하는 CUE만 지원합니다. CHD 또는 원본 단일 BIN을 선택하세요.')
        return (source.parent/names[0]).resolve()
    if suffix=='.bin':return source
    raise ValueError('원본 CHD, BIN 또는 CUE 파일을 선택하세요.')

def patch_bin(source,patch,output,m,log):
    if source.stat().st_size!=m['source_size']:raise ValueError('지원 일본판 원본과 파일 크기가 다릅니다.')
    log('일본판 원본 확인 중…')
    if sha(source)!=m['source_sha256']:raise ValueError('지원 원본의 SHA-256과 다릅니다. 이전 한글판이 아닌 일본판 원본을 선택하세요.')
    payload=zlib.decompress(patch.read_bytes())
    if len(payload)<80 or payload[:8]!=b'COBRAKR1':raise ValueError('패치 형식이 올바르지 않습니다.')
    length,count=struct.unpack_from('<II',payload,72)
    if length!=m['source_size'] or len(payload)!=80+count*2356 or payload[8:40].hex()!=m['source_sha256'] or payload[40:72].hex()!=m['target_sha256']:
        raise ValueError('패치 정보가 일치하지 않습니다.')
    log('한국어판 BIN 생성 중…')
    with source.open('rb') as src,output.open('xb') as dst:shutil.copyfileobj(src,dst,4*1024*1024)
    seen=set()
    with output.open('r+b') as f:
        for i in range(count):
            at=80+i*2356;sector=struct.unpack_from('<I',payload,at)[0]
            if sector in seen or (sector+1)*2352>length:raise ValueError('손상된 패치 섹터입니다.')
            seen.add(sector);f.seek(sector*2352);f.write(payload[at+4:at+2356])
    log('패치 결과 확인 중…')
    if sha(output)!=m['target_sha256']:raise ValueError('패치 결과 검증에 실패했습니다.')

def apply(source,output,make_chd=True,log=lambda text:None):
    m=assets();source=Path(source).expanduser().resolve();output=Path(output).expanduser().resolve()
    if not source.is_file():raise FileNotFoundError('원본 게임 파일을 찾을 수 없습니다.')
    if output.exists():raise FileExistsError('출력 폴더가 이미 있습니다. 새 폴더 이름을 지정하세요.')
    if output==source or output in source.parents:raise ValueError('원본 파일과 다른 새 출력 폴더를 지정하세요.')
    output.parent.mkdir(parents=True,exist_ok=True)
    if shutil.disk_usage(output.parent).free<900_000_000:raise ValueError('출력 드라이브에 900MB 이상의 여유 공간이 필요합니다.')
    with tempfile.TemporaryDirectory(prefix='.cobra-v0855-',dir=output.parent) as tmp:
        work=Path(tmp);payload=work/'result';payload.mkdir()
        original=source_bin(source,work,log)
        target=payload/(NAME+'.bin');patch_bin(original,RES/'patch.ckp',target,m,log)
        cue=payload/(NAME+'.cue')
        cue.write_text((RES/'output.cue').read_text(encoding='utf-8').replace('cobra-ko-experimental.bin',target.name),encoding='utf-8',newline='\n')
        report={'version':VERSION,'success':True,'source_sha256':m['source_sha256'],'output_bin_sha256':sha(target),'original_modified':False,'files':[target.name,cue.name]}
        if make_chd:
            chd=payload/(NAME+'.chd');log('한국어판 CHD 압축 중…')
            run([RES/'chdman.exe','createcd','-i',cue,'-o',chd]);log('CHD 무결성 확인 중…')
            run([RES/'chdman.exe','verify','-i',chd])
            report.update(output_chd_sha256=sha(chd),chd_verified=True);report['files'].append(chd.name)
        (payload/'patch-result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        if output.exists():raise FileExistsError('출력 폴더가 생성되어 작업을 중단했습니다. 다른 폴더를 선택하세요.')
        # Windows rename rejects an existing destination. Only our new result
        # directory is moved; source images are never opened for writing.
        payload.rename(output)
    log('완료! '+str(output))
    return dict(report,output=str(output))

def gui():
    import tkinter as tk
    from tkinter import ttk,filedialog,messagebox
    root=tk.Tk();root.title('PCE 스페이스 코브라 한국어 패치 v0.855');root.geometry('780x590');root.minsize(740,570)
    root.option_add('*Font',('맑은 고딕',10));style=ttk.Style(root);style.theme_use('clam')
    style.configure('TButton',padding=7);style.configure('Title.TLabel',font=('맑은 고딕',18,'bold'))
    main=ttk.Frame(root,padding=24);main.pack(fill='both',expand=True);main.columnconfigure(0,weight=1)
    header=ttk.Frame(main);header.grid(row=0,column=0,columnspan=2,sticky='ew',pady=(0,18))
    picture=tk.PhotoImage(file=str(RES/'title.png')).subsample(2,2)
    ttk.Label(header,image=picture).pack(side='left',padx=(0,20))
    words=ttk.Frame(header);words.pack(side='left',fill='x',expand=True)
    ttk.Label(words,text='스페이스 코브라',style='Title.TLabel').pack(anchor='w')
    ttk.Label(words,text='흑룡왕의 전설 · 한국어 패치 v0.855').pack(anchor='w',pady=(4,10))
    ttk.Label(words,text='일본판 원본 CHD 또는 단일 BIN/CUE를 선택하세요.\n새 폴더에 한국어판을 생성합니다.').pack(anchor='w')
    src=tk.StringVar();dst=tk.StringVar();chd=tk.BooleanVar(value=True);events=queue.Queue();busy=False
    def choose_source():
        value=filedialog.askopenfilename(title='일본판 원본 선택',filetypes=[('게임 이미지','*.chd *.cue *.bin'),('모든 파일','*.*')])
        if value:
            src.set(value)
            if not dst.get():dst.set(str(Path(value).parent/NAME))
    def choose_output():
        value=filedialog.askdirectory(title='새 결과 폴더를 만들 위치 선택')
        if value:dst.set(str(Path(value)/NAME))
    ttk.Label(main,text='원본 게임 파일').grid(row=1,column=0,sticky='w')
    a=ttk.Entry(main,textvariable=src);a.grid(row=2,column=0,sticky='ew',pady=(5,14))
    pick=ttk.Button(main,text='파일 선택',command=choose_source);pick.grid(row=2,column=1,padx=(10,0),pady=(5,14))
    ttk.Label(main,text='새 출력 폴더').grid(row=3,column=0,sticky='w')
    z=ttk.Entry(main,textvariable=dst);z.grid(row=4,column=0,sticky='ew',pady=(5,10))
    dest=ttk.Button(main,text='위치 선택',command=choose_output);dest.grid(row=4,column=1,padx=(10,0),pady=(5,10))
    option=ttk.Checkbutton(main,text='CHD도 생성하기 (BIN/CUE와 함께 저장)',variable=chd);option.grid(row=5,column=0,columnspan=2,sticky='w')
    ttk.Label(main,text='실행에는 Super CD-ROM² System Card 3.0이 필요합니다.').grid(row=6,column=0,columnspan=2,sticky='w',pady=(9,10))
    status=tk.StringVar(value='원본 파일을 선택하면 시작할 수 있습니다.')
    bar=ttk.Progressbar(main,mode='indeterminate');bar.grid(row=7,column=0,columnspan=2,sticky='ew',pady=(0,8))
    ttk.Label(main,textvariable=status,wraplength=700).grid(row=8,column=0,columnspan=2,sticky='w')
    def start():
        nonlocal busy
        if not src.get() or not dst.get():messagebox.showinfo('파일 선택','원본 파일과 새 출력 폴더를 지정하세요.');return
        inputs=(src.get(),dst.get(),chd.get());busy=True
        for widget in controls:widget.configure(state='disabled')
        bar.start(15)
        def worker():
            try:events.put(('done',apply(*inputs,log=lambda text:events.put(('status',text)))))
            except Exception as e:events.put(('error',str(e)))
        threading.Thread(target=worker,daemon=True).start()
    button=ttk.Button(main,text='한국어 패치 만들기',command=start);button.grid(row=9,column=0,columnspan=2,sticky='ew',pady=(22,0))
    controls=[a,z,pick,dest,option,button]
    def poll():
        nonlocal busy
        try:
            while True:
                kind,value=events.get_nowait()
                if kind=='status':status.set(value);continue
                busy=False;bar.stop()
                for widget in controls:widget.configure(state='normal')
                if kind=='done':
                    status.set('완료! '+value['output']);messagebox.showinfo('패치 완료','한국어판을 만들었습니다.\n\n'+value['output']+'\n\n새 CHD 또는 CUE로 전원을 다시 켜서 실행하세요.')
                else:status.set('실패: '+value);messagebox.showerror('패치 실패',value)
        except queue.Empty:pass
        root.after(100,poll)
    def close():
        if busy:messagebox.showinfo('작업 중','패치 작업이 끝난 뒤 창을 닫아 주세요.')
        else:root.destroy()
    root.protocol('WM_DELETE_WINDOW',close);poll();root.mainloop()

def main():
    parser=argparse.ArgumentParser(description='PCE Space Adventure Cobra KR v0.855 patcher')
    parser.add_argument('--input',type=Path);parser.add_argument('--output',type=Path)
    parser.add_argument('--no-chd',action='store_true');parser.add_argument('--report',type=Path)
    parser.add_argument('--self-test',action='store_true');args=parser.parse_args()
    # Automation reports also must never overwrite an existing user file.
    if args.report and args.report.exists():
        if sys.stderr:print('보고서 경로가 이미 있습니다.',file=sys.stderr)
        return 1
    if not args.input and not args.self_test:gui();return 0
    try:
        if args.self_test:
            m=assets();result={'success':True,'version':VERSION,'frozen':bool(getattr(sys,'frozen',False)),'assets_verified':True,'target_sha256':m['target_sha256']}
        else:
            if args.output is None:raise ValueError('--output 새 폴더가 필요합니다.')
            result=apply(args.input,args.output,not args.no_chd,log=lambda s:print(s,flush=True) if sys.stdout else None)
    except Exception as e:result={'success':False,'error':str(e)}
    if args.report:
        args.report.parent.mkdir(parents=True,exist_ok=True)
        with args.report.open('x',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=False,indent=2)
    if sys.stdout:print(json.dumps(result,ensure_ascii=False))
    return 0 if result['success'] else 1
if __name__=='__main__':raise SystemExit(main())
