lines = open(r'C:\Users\Lesia Eden\.gemini\antigravity\brain\f317caa6-a195-4fed-821e-2128aa1dc4c7\.system_generated\steps\272\output.txt', encoding='utf-8').readlines()
with open(r'c:\Users\Lesia Eden\Downloads\keystone-cowork\.agents\teamwork\spec_miner_o5_survey_1\cell8_extracted.txt', 'w', encoding='utf-8') as out:
    for l in lines:
        out.write(l)
print(f"Written {len(lines)} lines to cell8_extracted.txt")
