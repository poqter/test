"""One snapshot supplies both customer and advisor exports."""
import csv
import io
from modules.calculators.finance.finance_calculator_ui import csv_safe

def build_exports(name,fields,values,result,stamp):
 display=result.display()
 inputs=[(f'{f[0]} ({f[2]})',str(v)) for f,v in zip(fields,values)]
 customer='화랑 WORKSPACE · '+name+'\n계산 시각: '+stamp+'\n\n'+'\n'.join(k+': '+v for k,v in display.items())+'\n\n계산에 사용한 입력\n'+'\n'.join(k+': '+v for k,v in inputs)+'\n\n'+'\n'.join(result.assumptions)
 out=io.StringIO();writer=csv.writer(out)
 for row in [('계산기',name),('계산 시각',stamp),*inputs,*display.items(),('산식',result.formula),*[('가정',x) for x in result.assumptions]]:writer.writerow([csv_safe(x) for x in row])
 if result.rows:
  keys=list(dict.fromkeys(key for row in result.rows for key in row));writer.writerow(keys)
  writer.writerows([[csv_safe(row.get(k,'')) for k in keys] for row in result.rows])
 return customer,out.getvalue().encode('utf-8-sig')

# Compatibility API consumed by existing customer materials and legacy calculator tests.
from modules.calculators.legacy_calculator_exports import formatted_results, export_bytes
