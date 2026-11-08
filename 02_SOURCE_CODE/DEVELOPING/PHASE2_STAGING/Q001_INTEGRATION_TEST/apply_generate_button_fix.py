from pathlib import Path
import re
import py_compile

path = Path("app_phase2_shortlisting_v2.py")
backup = Path("app_phase2_shortlisting_v2.py.before_generate_button_fix")

if not backup.exists():
    raise SystemExit("STOP: Expected backup is missing.")

source = path.read_text(encoding="utf-8")

button = '<button type="button" onclick="generatePaper()" style="background:#16803c">Generate Question Paper + Code</button>'

if button not in source:
    anchor = '<button type="button" onclick="previewPaper()" style="background:#6c5ce7">Preview Paper</button>'
    if source.count(anchor) != 1:
        raise SystemExit("STOP: Preview button anchor not unique; no changes made.")
    source = source.replace(anchor, anchor + "\n" + button, 1)

pattern = r"(?m)^function generatePaper\(\) \{.*?^\}"
matches = list(re.finditer(pattern, source, re.S))

if len(matches) != 1:
    raise SystemExit(f"STOP: Expected one generatePaper function; found {len(matches)}.")

new_function = r"""function generatePaper() {
    var result = document.getElementById('result');
    var school = document.getElementById('school_code').value.trim();
    var board = document.getElementById('board_id').value;
    var cls = document.getElementById('class_level').value;
    var sub = document.getElementById('subject').value;
    var qty = document.getElementById('student_qty').value;
    var photo = document.getElementById('photostat').value;

    if (!school) {
        result.textContent = 'Please enter the School Code.';
        return;
    }
    if (!shortlistIds.length) {
        result.textContent = 'Please select at least one question from the Question Bank.';
        return;
    }

    var selected = shortlistIds.map(function(id) {
        return {
            id: Number(id),
            marks: parseInt(marksByQuestionId[String(id)] || '1', 10) || 1
        };
    });

    result.textContent = 'Generating paper and code...';

    var form = new FormData();
    form.append('school_code', school);
    form.append('board_id', board);
    form.append('class_level', cls);
    form.append('subject', sub);
    form.append('student_qty', qty);
    form.append('photostat', photo);
    form.append('question_selection', JSON.stringify(selected));

    fetch('/generate', { method: 'POST', body: form })
    .then(function(response) {
        return response.json().then(function(data) {
            if (!response.ok || data.error || !data.code) {
                throw new Error(data.error || 'Demo/code generation failed.');
            }
            return data;
        });
    })
    .then(function(data) {
        result.textContent = 'Code ' + data.code + ' created. Generating Actual Word paper...';

        return fetch('/actual/' + encodeURIComponent(data.code))
        .then(function(response) {
            return response.text().then(function(body) {
                if (!response.ok) {
                    var message = body;
                    try {
                        var parsedError = JSON.parse(body);
                        message = parsedError.error || body;
                    } catch (_) {}
                    throw new Error('Code ' + data.code + ' was created, but Actual generation failed: ' + message);
                }
                return { body: body, code: data.code };
            });
        });
    })
    .then(function(actual) {
        var parsed = new DOMParser().parseFromString(actual.body, 'text/html');
        var link = parsed.querySelector('a[href*="/download/"]');

        if (!link) {
            var message = actual.body;
            try {
                var errorData = JSON.parse(actual.body);
                message = errorData.error || actual.body;
            } catch (_) {}
            throw new Error('Code ' + actual.code + ' was created, but no Actual download link was returned: ' + message);
        }

        var href = link.getAttribute('href');
        var filename = link.textContent.trim();

        result.replaceChildren();

        var codeLine = document.createElement('p');
        codeLine.textContent = 'Paper Code: ' + actual.code;
        result.appendChild(codeLine);

        var downloadLink = document.createElement('a');
        downloadLink.href = href;
        downloadLink.textContent = 'Download Actual Word Paper: ' + filename;
        result.appendChild(downloadLink);

        var demoNote = document.createElement('p');
        demoNote.textContent = 'Actual paper generated successfully.';
        result.appendChild(demoNote);
    })
    .catch(function(error) {
        result.textContent = 'Generation status: ' + error.message;
    });
}"""

match = matches[0]
patched = source[:match.start()] + new_function + source[match.end():]

# Validate Python syntax before writing.
compile(patched, str(path), "exec")
path.write_text(patched, encoding="utf-8")
py_compile.compile(str(path), doraise=True)

print("PATCH APPLIED AND PYTHON SYNTAX PASSED.")
print("Added Generate Question Paper + Code button.")
print("Connected shortlistIds/marksByQuestionId to /generate and /actual.")
print("Backup retained at:", backup)
