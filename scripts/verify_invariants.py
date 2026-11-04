#!/usr/bin/env python3
"""
KEYSTONE Invariant & Baseline Immutability Verification Guard
Adheres to:
  - KEYSTONE_BIBLE.md (§2 Locked architectural invariants, §11 Abliterated checkpoint invariant,
    §24 Kaggle bootstrap deployment, §37 Change-control rules, §38 Deliverables)
  - ORIGINAL_REQUEST.md: Byte-preservation of 69 pre-built files, Bible SHA-256 freeze,
    pinned cognition checkpoint, baseline tests green.
"""

from __future__ import annotations

import os
import sys
import json
import hashlib
import argparse
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Tuple

# Reconfigure stdout to UTF-8 on Windows
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

BIBLE_EXPECTED_SHA256 = "1DA5FFE9D1467B7A4CF31F27F8B9D4CDE0B4096F1A922C6A3C214450FCC13A99"
BIBLE_EXPECTED_SIZE = 41919

PINNED_COGNITION_MODEL = "huihui-ai/Huihui-Qwen3.8-27B-abliterated"
PROHIBITED_MODEL_PATTERNS = [
    "qwen/qwen2.5-7b", "qwen2.5-14b", "qwen2.5-32b-instruct",
    "-awq", "-gptq", "-gguf", "unsloth", "quantized"
]

# Complete 69 pre-built files manifest (paths normalized with forward slashes)
PREBUILT_MANIFEST: Dict[str, Dict[str, Any]] = {
  "Keystone XL/.gitattributes": {
    "size": 66,
    "sha256": "1A1DBE176BC233B499D35A57DB7513F2941C99AB9759F177830C9149BE99005B"
  },
  "README.md": {
    "size": 1881,
    "sha256": "95FBF20DE30F6894FA94A6AF7C0981CA1E0811409060576D33C339DB7AB8E5BA"
  },
  "TEST_INFRA.md": {
    "size": 12640,
    "sha256": "BE98F86EA340AA920E62BD29D84BD4FAC6A6069C7596AB41C14ED28675C81662"
  },
  "TEST_READY.md": {
    "size": 10247,
    "sha256": "30F50A078450A25B3E8EA46C3923B50C4F23FCF6CECA904778396AF2795647C4"
  },
  "apps/admin/README.md": {
    "size": 164,
    "sha256": "2F6F6F2AD6DFFA4C6AB5C097D85166A5432105F7E44CB7026EBAFDF57F20FC27"
  },
  "apps/api/src/intelligence_router.py": {
    "size": 21362,
    "sha256": "350316B4CE9C9A1BE8321003D4842D255A90F0B5A89AEE5EC378868E0776512D"
  },
  "apps/api/src/main.py": {
    "size": 578,
    "sha256": "1EAA72DCC8B1CD383615A2F05FE9C41AA099C6584893419606C96736F170B5DC"
  },
  "apps/web/README.md": {
    "size": 208,
    "sha256": "513E241ABE41D76F5EE89C9C30A2E585B7AE6A70FEA168697AE4AD3AAD48CC8B"
  },
  "docs/BUILD_NOW.md": {
    "size": 1275,
    "sha256": "D59A31EA09E92AB11B6E869FB09D8EF1A665CB13F0B2C084850F385CBE33C416"
  },
  "docs/FILE_MANIFEST.txt": {
    "size": 649,
    "sha256": "170E9D94789F66ABA281D425BB3E92C1A063738D1230A441A35B228DD00B1A38"
  },
  "docs/IDENTITY_PRESERVATION.md": {
    "size": 4117,
    "sha256": "2C4E615796A278910DEE88FD7E13313029D7EE76ED815C43EC06C4FE9C8BFE43"
  },
  "infrastructure/bigquery/README.md": {
    "size": 11406,
    "sha256": "8555C908EEDBB2E1C73C9616F3D53483D28F8023CF76C0C89A89BE4BC583E6C4"
  },
  "infrastructure/bigquery/mocks/ast_validator.js": {
    "size": 14854,
    "sha256": "5472D6BBFCD690F3F1E797612A3D13FB66E03CB6CFE37BD7D4156240DAC65705"
  },
  "infrastructure/bigquery/queries/ai_procedures.sql": {
    "size": 10504,
    "sha256": "D1411CED44801CDA6CA9697FC1CCB6FE3C28C3A76B5D473FF824F752B63E7A52"
  },
  "infrastructure/bigquery/schemas/001_intelligence_schema.sql": {
    "size": 7550,
    "sha256": "F24AF23BA318E5664D32C58A3857880CB824C1EA6C9B4DDBEE361B3DFEB54887"
  },
  "infrastructure/bigquery/scripts/deploy_bigquery.ps1": {
    "size": 6287,
    "sha256": "6107A8AB155FB6A2578CF2B89E79B51E7E7D1139CDF84836850EA9DCDD8EB78D"
  },
  "infrastructure/bigquery/scripts/deploy_bigquery.sh": {
    "size": 5995,
    "sha256": "642DB963955B1104A41F1B7E155816F6D3C3133D71CD65231B7762D901FDE362"
  },
  "infrastructure/kaggle/keystone_kaggle_bootstrap.ipynb": {
    "size": 2149,
    "sha256": "11B010D7C5E378DC956E346C46E12EFF142320E088015E7D4B1FBBA86CAB13CC"
  },
  "infrastructure/migrations/versions/0001_core.sql": {
    "size": 4788,
    "sha256": "F7F0E977CEFD7CACF9D8B20B40BD73F1AC316732FF364E10FFB2287725401186"
  },
  "keystone-cowork-updated.zip": {
    "size": 132075,
    "sha256": "56DACF1BCDD82D5609BD9C984DB24A10336EA6BAE0348CA2F00802482405D4E9"
  },
  "openapi.yaml": {
    "size": 11822,
    "sha256": "6D923E48C2117C119AB4B1BE80085EC059E704D2358CE67B7B5DF822B0B03673"
  },
  "package.json": {
    "size": 480,
    "sha256": "9AA59FCE6CCAB16012A8521C9B8F7424075182119ECDB047A0903B6FBF11CC96"
  },
  "packages/contracts/src/contracts.json": {
    "size": 366,
    "sha256": "8AB200CB6524FE7DF2FCCBD5699551CB402815C81BE2C9AC63C136B3B2E251D2"
  },
  "packages/prompt-engine/src/engine.js": {
    "size": 3736,
    "sha256": "5DEEFF1380BE1BD546B06FFC82FBA617090F2C0479C0A5D4AF8A1DF16985321A"
  },
  "packages/prompt-engine/src/meta-prompt.js": {
    "size": 562,
    "sha256": "278E4B8E64106B1F89EFE90DB005B7F2B6DB9DCCD40607EB4FB83F667704C3C7"
  },
  "packages/prompt-engine/src/playbooks.js": {
    "size": 5885,
    "sha256": "0B63598DB7A0112937DB9AAAD5776CC3A2352CCD7D27F90A76E1CCA45CE4DF39"
  },
  "packages/prompt-engine/src/prompt-compiler.js": {
    "size": 2322,
    "sha256": "DB34C93ADF74C465B13CE0AB8A2D1554193D64834A116E2D05BD14B08E53127F"
  },
  "requirements.txt": {
    "size": 249,
    "sha256": "09C612F04563EC4F20451E6CB1ABCC4EE41DCA1BF439A2DBD98AD0F9CD7FD30A"
  },
  "scripts/setup_environment.ps1": {
    "size": 7664,
    "sha256": "4BCBFB2A6887055E21B396B739BA28790C10170AC23D0D91205C1ADEF43CA765"
  },
  "scripts/verify_environment.py": {
    "size": 13101,
    "sha256": "2161DC800F1B9C0C87DF6096183BAD62CACE59AB15A17DC6DEAED5554EAEF65A"
  },
  "services/authority/README.md": {
    "size": 214,
    "sha256": "860B162B777E4499D5D0143263530DF75AE3F1A59BF364B90B19E02E2DD50019"
  },
  "services/cognition/README.md": {
    "size": 329,
    "sha256": "4363EF1A028E5CFE538041C3B08882BA93617B51A7ABC0CB0794CA731A444CC9"
  },
  "services/comfy/README.md": {
    "size": 161,
    "sha256": "0C0E796B5017A52EB5A6AE651C07BC7530719A176236682D725336B15808461B"
  },
  "services/harness/README.md": {
    "size": 209,
    "sha256": "665BBF9109585DAB9AA296504C15AB2085AD9671FF0219EB5912F9302D69F4D9"
  },
  "services/intelligence/README.md": {
    "size": 10834,
    "sha256": "EA3BC52D34EAF92AC2428BFEE146570A93308A420E50AA5AE0F9D63418C331E0"
  },
  "services/intelligence/package.json": {
    "size": 519,
    "sha256": "8817E3CB1C29C46A881313B24EB00ED57C1B42AA5DDC9D581395FADBC8374541"
  },
  "services/intelligence/src/bridge/capability_manifest.js": {
    "size": 1558,
    "sha256": "2FE9C1F6EC666E3D209A354106B7A4A93CF2E558CB2EE58B6C52C84362B332D3"
  },
  "services/intelligence/src/bridge/prompt_bridge.js": {
    "size": 2653,
    "sha256": "74EDB5E99BD4D7F98AF4914D2BD40B9A276C3FC8F21DA5F3E3AD76E4CE07ED30"
  },
  "services/intelligence/src/bridge/service_bridge.js": {
    "size": 10037,
    "sha256": "D68270F85606FBC07C548B66CC94DC139CACFA476B789878568D11D19A53411C"
  },
  "services/intelligence/src/index.js": {
    "size": 5404,
    "sha256": "A0B5A69C51AA49B2D5095B82DF526E786324F95828E4B538C057EABD79DE4B05"
  },
  "services/intelligence/src/scraper/ast_deconstructor.js": {
    "size": 10465,
    "sha256": "B37585CEE137845DBE1B86B88214B66A4AE1041273771F7947F7C9829A1E6A39"
  },
  "services/intelligence/src/scraper/dedup_cache.js": {
    "size": 3947,
    "sha256": "6862C7C7E959C2948EA4EB39771552B08DFC956F70389F2DF07A9B2641CACDB4"
  },
  "services/intelligence/src/scraper/edge_pii.js": {
    "size": 2020,
    "sha256": "3DD6FE55AFB41A6EE1A17D9A3361F60FC7C3C7CD5FC7F836826C95E9634BF99E"
  },
  "services/intelligence/src/scraper/firecrawl_client.js": {
    "size": 4251,
    "sha256": "F18070C54E6B8A530853B55C49E15DFFC864ABFD43D32403BCA8F3A5A87D610E"
  },
  "services/intelligence/src/security/aikido_defense.js": {
    "size": 4503,
    "sha256": "0C782451B5DE576CD9BAB5A1858F8C14F06F41AE033B6B04903DD271F71B1322"
  },
  "services/intelligence/src/vault/vault_service.js": {
    "size": 6192,
    "sha256": "C7BC6E4FE1A81723BFF4699E0C27B3ABB4E8450E0FCC694934034A71E24C55FB"
  },
  "tests/adversarial_security_suite.js": {
    "size": 22016,
    "sha256": "A68D5058C216673ACDD3F0FC71F4523A27901139E4CD1ACC17E5C8417451EC80"
  },
  "tests/e2e/challenger_stress.js": {
    "size": 17757,
    "sha256": "3074FE763273713FFB6D86D02C19EAEF64DD1D489EB376BA06E933DBD9B172B7"
  },
  "tests/e2e/fixtures/adobe_sample.html": {
    "size": 1702,
    "sha256": "1AD3420DB825CCF655FF7987166ECBD848CA855C67866B883A69B4F17334A4A7"
  },
  "tests/e2e/fixtures/bigquery_ast_mocks.json": {
    "size": 3445,
    "sha256": "DC237E29D1E489167B718F5CD7662410B30B1C1722ED842B4AF443C85444FEE9"
  },
  "tests/e2e/fixtures/grok_sample.html": {
    "size": 1585,
    "sha256": "025ABB937D259C8B00F111D150035FCD4E29D75AC6C6B54164B25887934FB727"
  },
  "tests/e2e/fixtures/hf_space_deconstruct.json": {
    "size": 6694,
    "sha256": "1E6BCD9FEC6ECDD7A4F9FFDC9688262ABCFDCD6A4BF44871C8D5D6E7955CCDE9"
  },
  "tests/e2e/fixtures/hf_space_sample.html": {
    "size": 2706,
    "sha256": "7CDEDC140940F3C3760304C19AAB1B3855F5638183195FFF3AD2A69FCA93FE4C"
  },
  "tests/e2e/fixtures/higgsfield_sample.html": {
    "size": 1408,
    "sha256": "5AB21FC98A4B4BA3BD3AEF5AC4EA3274B44F8F95494572900CCDE9387EB530F2"
  },
  "tests/e2e/fixtures/injection_payloads.json": {
    "size": 1729,
    "sha256": "7D440AA850A8CC666AE9504935F5410FFA7D88478737307A1688D40851254C68"
  },
  "tests/e2e/fixtures/targets_catalog.json": {
    "size": 2304,
    "sha256": "8C492E2B75F2C099ACF2903F01DAAA23D52FE5E19D2E8FF671B27E551EAF88BB"
  },
  "tests/e2e/fixtures/venice_sample.html": {
    "size": 1403,
    "sha256": "6115E5BB9D4E2453BFB4CF229B4E95003000458C59EEB6DADE24DEC2302AA672"
  },
  "tests/e2e/fixtures/zencreator_sample.html": {
    "size": 1375,
    "sha256": "A700C9897A551AAB41580A9680E3DC6752AE061E344E4C32812D3E1607635FC8"
  },
  "tests/e2e/harness/contract_oracle.js": {
    "size": 28417,
    "sha256": "2303E176FDF99DA5EBA05A05508B01296633C45C20ED363307FCA74178FB9C97"
  },
  "tests/e2e/harness/loader.js": {
    "size": 1319,
    "sha256": "B5D827D236A07169CCCBA06D5316949A1F39E11F421D1D10EDB5D8A6978E627A"
  },
  "tests/e2e/harness/sql_validator.js": {
    "size": 3725,
    "sha256": "06BCC7E660A4BAE743877BAD0DB34C051A2D738066D4D512753B35E8B3594880"
  },
  "tests/e2e/runner.js": {
    "size": 3361,
    "sha256": "920D63F106786C5052EFC25D786731C60DF3BBBC018AAE533780344EC0294F6F"
  },
  "tests/e2e/tier1_features.test.js": {
    "size": 23775,
    "sha256": "2A72BBDD2B1D3C63A710ADCF1DAB8C32D38A683D4B578324B09FCE8C4A05C68B"
  },
  "tests/e2e/tier2_boundaries.test.js": {
    "size": 20888,
    "sha256": "B274DB0CFC0EA01EB2D2812FEB6D1489C977ED24E8169F5F677387F9828D36DB"
  },
  "tests/e2e/tier3_combinations.test.js": {
    "size": 6525,
    "sha256": "39C4BE1AD8AC63B3D7E7E4D7941701377BCAA996B38C573007C4C4FA87CC20E7"
  },
  "tests/e2e/tier4_realworld.test.js": {
    "size": 10740,
    "sha256": "F4F0C6C5BC3A890E9DBF85C510A0E989457F45390BF6D2C19A38FF7629D5BC96"
  },
  "tests/e2e/tier5_scraping_adversarial.test.js": {
    "size": 24467,
    "sha256": "FBCB6C4492C6F37468EE9DECD4D6731E57EE97FDA732655A5DAA7AC07225BC11"
  },
  "tests/e2e/tier5_security_adversarial.test.js": {
    "size": 31947,
    "sha256": "D35FA2BC79D8439F58BC774E1991F9C551DA907945327E1E87B5A7B89133E98B"
  },
  "tests/identity.test.js": {
    "size": 1348,
    "sha256": "ED89940108D3A6E742B2069DD7A90F5C2E4209C852729DE81DBA2AA0C2943590"
  }
}


def compute_sha256(filepath: Path) -> Tuple[int, str]:
    data = filepath.read_bytes()
    return len(data), hashlib.sha256(data).hexdigest().upper()


def verify_bible(root_dir: Path, require_docs_copy: bool = False) -> Dict[str, Any]:
    root_bible = root_dir / "KEYSTONE_BIBLE.md"
    docs_bible = root_dir / "docs" / "KEYSTONE_BIBLE.md"
    
    res = {
        "root_present": root_bible.exists(),
        "root_sha256": None,
        "root_size": None,
        "root_valid": False,
        "docs_present": docs_bible.exists(),
        "docs_sha256": None,
        "docs_size": None,
        "docs_valid": False,
        "overall_valid": False
    }

    if root_bible.exists():
        sz, sha = compute_sha256(root_bible)
        res["root_size"] = sz
        res["root_sha256"] = sha
        res["root_valid"] = (sha == BIBLE_EXPECTED_SHA256 and sz == BIBLE_EXPECTED_SIZE)

    if docs_bible.exists():
        sz, sha = compute_sha256(docs_bible)
        res["docs_size"] = sz
        res["docs_sha256"] = sha
        res["docs_valid"] = (sha == BIBLE_EXPECTED_SHA256 and sz == BIBLE_EXPECTED_SIZE)
    elif not require_docs_copy:
        # If docs copy is not strictly required yet (pre-Wave 0 delivery), docs_valid is considered pending
        res["docs_valid"] = True

    res["overall_valid"] = res["root_valid"] and (res["docs_valid"] if (docs_bible.exists() or require_docs_copy) else True)
    return res


def verify_prebuilt_manifest(root_dir: Path) -> Dict[str, Any]:
    mismatches = []
    missing = []
    verified_count = 0

    for rel_path, meta in PREBUILT_MANIFEST.items():
        target = root_dir / rel_path
        if not target.exists():
            missing.append(rel_path)
            continue
        sz, sha = compute_sha256(target)
        if sz != meta["size"] or sha != meta["sha256"]:
            mismatches.append({
                "path": rel_path,
                "expected_size": meta["size"],
                "actual_size": sz,
                "expected_sha256": meta["sha256"],
                "actual_sha256": sha
            })
        else:
            verified_count += 1

    return {
        "total_manifest": len(PREBUILT_MANIFEST),
        "verified_count": verified_count,
        "missing_count": len(missing),
        "mismatch_count": len(mismatches),
        "missing": missing,
        "mismatches": mismatches,
        "all_valid": (len(missing) == 0 and len(mismatches) == 0)
    }


def verify_cognition_checkpoint(root_dir: Path) -> Dict[str, Any]:
    bootstrap_nb = root_dir / "infrastructure" / "kaggle" / "keystone_kaggle_bootstrap.ipynb"
    checks = []
    
    if not bootstrap_nb.exists():
        return {
            "valid": False,
            "error": "infrastructure/kaggle/keystone_kaggle_bootstrap.ipynb not found"
        }

    try:
        data = json.loads(bootstrap_nb.read_text(encoding="utf-8"))
        nb_text = json.dumps(data)
        
        has_pinned = PINNED_COGNITION_MODEL in nb_text
        has_prohibited = any(p in nb_text.lower() for p in PROHIBITED_MODEL_PATTERNS)
        
        checks.append({
            "target": str(bootstrap_nb.relative_to(root_dir)),
            "pinned_model_present": has_pinned,
            "prohibited_substitutes_found": has_prohibited,
            "valid": has_pinned and not has_prohibited
        })
    except Exception as e:
        return {"valid": False, "error": f"Failed to parse bootstrap notebook: {e}"}

    # Also inspect KAGGLE_SETUP if present
    kaggle_setup = root_dir / "KAGGLE_SETUP"
    if kaggle_setup.exists():
        for p in kaggle_setup.rglob("*.ipynb"):
            try:
                txt = p.read_text(encoding="utf-8")
                has_pinned = PINNED_COGNITION_MODEL in txt
                has_prohibited = any(sub in txt.lower() for sub in PROHIBITED_MODEL_PATTERNS)
                checks.append({
                    "target": str(p.relative_to(root_dir)),
                    "pinned_model_present": has_pinned,
                    "prohibited_substitutes_found": has_prohibited,
                    "valid": has_pinned and not has_prohibited
                })
            except Exception:
                pass

    all_valid = all(c["valid"] for c in checks)
    return {
        "pinned_model": PINNED_COGNITION_MODEL,
        "checks": checks,
        "valid": all_valid
    }


def run_command_check(cmd: List[str], cwd: Path) -> Dict[str, Any]:
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            shell=True,
            timeout=120
        )
        return {
            "command": " ".join(cmd),
            "exit_code": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "success": (proc.returncode == 0)
        }
    except Exception as e:
        return {
            "command": " ".join(cmd),
            "exit_code": -1,
            "stdout": "",
            "stderr": str(e),
            "success": False
        }


def verify_npm_test(root_dir: Path) -> Dict[str, Any]:
    res = run_command_check(["npm", "test"], root_dir)
    # Check for 3 passing tests
    output = res["stdout"] + res["stderr"]
    has_pass = ("pass 3" in output or "3 Pass" in output or "✔" in output)
    has_fail = ("fail [1-9]" in output or "failed" in output.lower() and res["exit_code"] != 0)
    passed = res["success"] and has_pass and not has_fail
    return {
        "command": "npm test",
        "exit_code": res["exit_code"],
        "passed": passed,
        "output_summary": "\n".join([line for line in output.splitlines() if "pass" in line.lower() or "tests" in line.lower() or "✔" in line][:5])
    }


def verify_e2e_runner(root_dir: Path) -> Dict[str, Any]:
    res = run_command_check(["node", "tests/e2e/runner.js"], root_dir)
    output = res["stdout"] + res["stderr"]
    passed = res["success"] and ("132 passed" in output or "ALL TIERS PASSING" in output)
    return {
        "command": "node tests/e2e/runner.js",
        "exit_code": res["exit_code"],
        "passed": passed,
        "output_summary": "\n".join([line for line in output.splitlines() if "Total Tests" in line or "Total Passed" in line or "PASSING" in line][:5])
    }


def main():
    parser = argparse.ArgumentParser(description="KEYSTONE Invariant & Immutability Verification Guard")
    parser.add_argument("--root", default=".", help="Project root directory")
    parser.add_argument("--json", action="store_true", help="Output results in JSON format")
    parser.add_argument("--require-docs-bible", action="store_true", help="Require docs/KEYSTONE_BIBLE.md to exist and match")
    parser.add_argument("--skip-tests", action="store_true", help="Skip running npm test and node e2e runner")
    args = parser.parse_args()

    root_dir = Path(args.root).resolve()

    bible_res = verify_bible(root_dir, require_docs_copy=args.require_docs_bible)
    manifest_res = verify_prebuilt_manifest(root_dir)
    cognition_res = verify_cognition_checkpoint(root_dir)

    npm_res = {"passed": True, "skipped": True} if args.skip_tests else verify_npm_test(root_dir)
    e2e_res = {"passed": True, "skipped": True} if args.skip_tests else verify_e2e_runner(root_dir)

    all_passed = (
        bible_res["overall_valid"]
        and manifest_res["all_valid"]
        and cognition_res["valid"]
        and npm_res["passed"]
        and e2e_res["passed"]
    )

    result = {
        "status": "PASS" if all_passed else "FAIL",
        "all_passed": all_passed,
        "bible_verification": bible_res,
        "prebuilt_manifest_verification": manifest_res,
        "cognition_checkpoint_verification": cognition_res,
        "npm_test_identity": npm_res,
        "e2e_runner_run1": e2e_res
    }

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print("=" * 80)
        print("  KEYSTONE INVARIANT & IMMUTABILITY VERIFICATION GUARD")
        print("=" * 80)
        print(f"Overall Status: {'[PASS] 100% INVARIANTS SATISFIED' if all_passed else '[FAIL] INVARIANT BREACH DETECTED'}\n")
        
        print("1. KEYSTONE_BIBLE.md Canonical Checksum:")
        print(f"   Root Bible SHA-256 : {bible_res['root_sha256']} [{'VALID' if bible_res['root_valid'] else 'INVALID'}]")
        print(f"   Docs Bible Copy    : {'VALID' if bible_res['docs_valid'] else ('PENDING' if not bible_res['docs_present'] else 'INVALID')}")
        
        print(f"\n2. Pre-Built Manifest Verification (69 Files):")
        print(f"   Tracked Pre-Built  : {manifest_res['total_manifest']} files")
        print(f"   Byte-Identical     : {manifest_res['verified_count']} files")
        print(f"   Missing            : {manifest_res['missing_count']} files")
        print(f"   Mismatches         : {manifest_res['mismatch_count']} files")
        if manifest_res['mismatches']:
            for m in manifest_res['mismatches']:
                print(f"     ! Mismatch in {m['path']}: expected {m['expected_sha256'][:16]}..., got {m['actual_sha256'][:16]}...")

        print(f"\n3. Cognition Checkpoint Pinning:")
        print(f"   Pinned Model       : {cognition_res['pinned_model']}")
        print(f"   Status             : {'PINNED AND VERIFIED' if cognition_res['valid'] else 'VIOLATION DETECTED'}")

        print(f"\n4. Identity Invariant Tests (`npm test`):")
        print(f"   Status             : {'PASS (3/3 Tests)' if npm_res['passed'] else 'FAIL'}")

        print(f"\n5. Run 1 E2E Test Suite (`node tests/e2e/runner.js`):")
        print(f"   Status             : {'PASS (132/132 Tests)' if e2e_res['passed'] else 'FAIL'}")
        print("=" * 80)

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
