#!/usr/bin/env python3
"""
Generate a Canvas-importable QTI 1.2 package (assessment.xml + imsmanifest.xml)
Reads questions from CSV or JSON input file.

Input format options:

Option A: CSV
Each row has:
    type,prompt,choice_A,choice_B,choice_C,choice_D,answer
Examples:
    mc,Which channel yields the most accurate comparisons?,Angle,Area,Color,Position or length,D
    tf,Scatter plots prove causation.,,,,F

Option B: JSON
A list of objects:
[
  {"type":"mc","prompt":"Which channel yields...","choices":{"A":"Angle","B":"Area","C":"Color","D":"Position or length"},"answer":"D"},
  {"type":"tf","prompt":"Scatter plots prove causation.","answer":"F"}
]


Usage:

# From CSV
python canvas-qti-creator.py questions.csv -o <OUTPUT>.zip --title "<QUIZ TITLE>"

# From JSON
python canvas-qti-creator.py questions.json -o <OUTPUT>.zip --title "<QUIZ TITLE>"

"""

import csv, json, os, zipfile
from xml.etree.ElementTree import Element, SubElement, ElementTree, tostring
import xml.dom.minidom


# ----------------- XML builders -----------------
def add_canvas_itemmeta(item, qtype, points="1"):
    itemmetadata = SubElement(item, "itemmetadata")
    qtimetadata = SubElement(itemmetadata, "qtimetadata")
    for k, v in [
        ("question_type", qtype),
        ("points_possible", points),
        ("assessment_question_identifier_ref", item.attrib["ident"]),
    ]:
        f = SubElement(qtimetadata, "qtimetadatafield")
        SubElement(f, "fieldlabel").text = k
        SubElement(f, "fieldentry").text = v

def mc_item(idx, prompt, choices, correct_ident):
    item = Element("item", {"ident": f"ITEM_{idx}", "title": f"Q{idx}"})
    add_canvas_itemmeta(item, "multiple_choice_question")

    pres = SubElement(item, "presentation")
    mat = SubElement(pres, "material")
    SubElement(mat, "mattext", {"texttype":"text/plain"}).text = str(prompt)

    resp = SubElement(pres, "response_lid", {"ident": f"RESP_{idx}", "rcardinality":"Single"})
    render = SubElement(resp, "render_choice", {"shuffle":"No"})
    for ident in ["A","B","C","D"]:
        rl = SubElement(render, "response_label", {"ident": ident})
        rmat = SubElement(rl, "material")
        SubElement(rmat, "mattext", {"texttype":"text/plain"}).text = str(choices[ident])

    rp = SubElement(item, "resprocessing")
    outcomes = SubElement(rp, "outcomes")
    SubElement(outcomes, "decvar", {"vartype":"Integer","defaultval":"0","minvalue":"0","maxvalue":"1"})

    rc_ok = SubElement(rp, "respcondition", {"continue_":"No"})
    cv_ok = SubElement(rc_ok, "conditionvar")
    SubElement(cv_ok, "varequal", {"respident": f"RESP_{idx}"}).text = correct_ident
    SubElement(rc_ok, "setvar", {"action":"Set"}).text = "1"

    rc_else = SubElement(rp, "respcondition", {"continue_":"Yes"})
    cv_else = SubElement(rc_else, "conditionvar"); SubElement(cv_else, "other")
    SubElement(rc_else, "setvar", {"action":"Set"}).text = "0"
    return item

def tf_item(idx, prompt, correct_ident):
    # correct_ident: "T" or "F"
    item = Element("item", {"ident": f"ITEM_{idx}", "title": f"Q{idx}"})
    add_canvas_itemmeta(item, "true_false_question")

    pres = SubElement(item, "presentation")
    mat = SubElement(pres, "material")
    SubElement(mat, "mattext", {"texttype":"text/plain"}).text = prompt
    resp = SubElement(pres, "response_lid", {"ident": f"RESP_{idx}", "rcardinality":"Single"})
    render = SubElement(resp, "render_choice", {"shuffle":"No"})
    for ident, text in [("T","True"), ("F","False")]:
        rl = SubElement(render, "response_label", {"ident": ident})
        rmat = SubElement(rl, "material")
        SubElement(rmat, "mattext", {"texttype":"text/plain"}).text = text

    rp = SubElement(item, "resprocessing")
    outcomes = SubElement(rp, "outcomes")
    SubElement(outcomes, "decvar", {"vartype":"Integer","defaultval":"0","minvalue":"0","maxvalue":"1"})

    rc_ok = SubElement(rp, "respcondition", {"continue_":"No"})
    cv_ok = SubElement(rc_ok, "conditionvar")
    SubElement(cv_ok, "varequal", {"respident": f"RESP_{idx}"}).text = correct_ident
    SubElement(rc_ok, "setvar", {"action":"Set"}).text = "1"

    rc_else = SubElement(rp, "respcondition", {"continue_":"Yes"})
    cv_else = SubElement(rc_else, "conditionvar")
    SubElement(cv_else, "other")
    SubElement(rc_else, "setvar", {"action":"Set"}).text = "0"
    return item

def write_assessment(items, out_xml="assessment.xml", title="Module Quiz"):
    qti = Element("questestinterop")
    assess = SubElement(qti, "assessment", {"ident":"A1", "title": title})

    # assessment-level qtimetadata (cc_maxattempts, cc_timelimit)
    qtimd = SubElement(assess, "qtimetadata")
    for k, v in [("cc_maxattempts","1"), ("cc_timelimit","12")]:
        f = SubElement(qtimd, "qtimetadatafield")
        SubElement(f, "fieldlabel").text = k
        SubElement(f, "fieldentry").text = v

    section = SubElement(assess, "section", {"ident":"root_section"})
    for it in items:
        section.append(it)
    ElementTree(qti).write(out_xml, encoding="utf-8", xml_declaration=True)
    return out_xml

def write_manifest(href="assessment.xml", out_xml="imsmanifest.xml"):
    manifest = Element(
        "manifest",
        {
            "xmlns": "http://www.imsglobal.org/xsd/imscp_v1p1",
            "xmlns:imsmd": "http://www.imsglobal.org/xsd/imsmd_v1p2",
            "xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance",
            "identifier": "MANIFEST1",
            "xsi:schemaLocation": "http://www.imsglobal.org/xsd/imscp_v1p1 imscp_v1p1.xsd",
        },
    )
    resources = SubElement(manifest, "resources")
    resource = SubElement(resources, "resource", {
        "identifier": "RES-1",
        "type": "imsqti_xmlv1p2",
        "href": href
    })
    SubElement(resource, "file", {"href": href})

    rough = tostring(manifest, encoding="utf-8")
    pretty = xml.dom.minidom.parseString(rough).toprettyxml(indent="  ", encoding="utf-8")
    with open(out_xml, "wb") as f:
        f.write(pretty)  
    return out_xml

def package_qti(assessment_xml, manifest_xml, out_zip):
    with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(assessment_xml, arcname="assessment.xml")
        z.write(manifest_xml, arcname="imsmanifest.xml")

    # delete temporary files after packaging
    if os.path.exists(assessment_xml):
        os.remove(assessment_xml)
    if os.path.exists(manifest_xml):
        os.remove(manifest_xml)
    
    return out_zip

# ----------------- Main logic -----------------
def load_questions(input_path):
    ext = os.path.splitext(input_path)[1].lower()
    questions = []
    if ext == ".csv":
        with open(input_path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                questions.append(row)
    elif ext == ".json":
        with open(input_path, encoding="utf-8") as f:
            questions = json.load(f)
    else:
        raise ValueError("Input must be .csv or .json")
    return questions

def build_qti_from_file(input_file, output_zip="quiz_qti.zip", title="Module Quiz"):
    questions = load_questions(input_file)
    items, idx = [], 1
    for q in questions:
        qtype = q["type"].strip().lower()

        if qtype == "mc":
            # JSON with nested {"choices": {...}} OR CSV with choice_A..choice_D
            if isinstance(q.get("choices"), dict):
                choices = {k: str(q["choices"].get(k, "")).strip() for k in ["A","B","C","D"]}
            else:
                choices = {k: str(q.get(f"choice_{k}", "")).strip() for k in ["A","B","C","D"]}

            missing = [k for k,v in choices.items() if not v]
            if missing:
                raise ValueError(f"MC Q{idx} missing text for options: {', '.join(missing)}")

            ans = q["answer"].strip().upper()[0]
            items.append(mc_item(idx, q["prompt"], choices, ans))

        elif qtype == "tf":
            ans = q["answer"].strip().upper()[0]  # T or F
            items.append(tf_item(idx, q["prompt"], ans))
        else:
            raise ValueError(f"Unsupported type at Q{idx}: {qtype}")

        idx += 1

    assess = write_assessment(items, "assessment.xml", title)
    mani = write_manifest("assessment.xml", "imsmanifest.xml")
    zipf = package_qti(assess, mani, output_zip)
    print(f"Created Canvas QTI package: {zipf}")

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Generate Canvas QTI package from CSV/JSON question file.")
    p.add_argument("input_file", help="Input CSV or JSON containing questions")
    p.add_argument("-o","--output", default="canvas_quiz.zip", help="Output zip filename")
    p.add_argument("--title", default="Module Quiz", help="Quiz title")
    args = p.parse_args()
    build_qti_from_file(args.input_file, args.output, args.title)
