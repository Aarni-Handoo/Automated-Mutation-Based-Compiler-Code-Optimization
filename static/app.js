'use strict';

const $ = id => document.getElementById(id);

const samples = {
    python: `def calculate(a: int, b: int):
    x = a + 0
    y = b * 1
    unused = 10 + 20
    z = x + y
    return z
`,
    tac: `t1 = a + 0
t2 = b * 1
t3 = 10 + 20
t4 = t1 + t2
result = t4 + t3
`
};

let result = null;
let bench = null;
let running = false;

const drafts = { ...samples };
let previousMode = 'python';

const esc = s =>
    String(s).replace(/[&<>"']/g, c => ({
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;'
    })[c]);

function error(message) {
    $('error').hidden = !message;
    $('error').textContent = message || '';
}

function lock(value) {
    running = value;

    $('run').disabled = value;
    $('benchmark').disabled = value;
    $('busy').hidden = !value;

    for (const id of ['mode', 'source', 'sample', 'file', 'outputs']) {
        $(id).disabled = value;
    }
}

async function api(url, body) {
    const response = await fetch(
        url,
        body === undefined
            ? {}
            : {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(body)
            }
    );

    const data = await response.json();

    if (!response.ok) {
        throw new Error(data.error || 'Request failed');
    }

    return data;
}

function save(name, text, type = 'text/plain') {
    const link = document.createElement('a');

    const url = URL.createObjectURL(
        new Blob([text], { type })
    );

    link.href = url;
    link.download = name;
    link.click();

    setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function clearResult() {
    result = null;

    $('results').hidden = true;
    $('optimized').textContent = 'Your selected candidate will appear here.';
    $('optimized').classList.add('empty');
    $('status').textContent = 'Ready';

    $('download').disabled = true;
    $('report').disabled = true;
}

$('source').value = samples.python;

$('mode').onchange = () => {
    drafts[previousMode] = $('source').value;

    previousMode = $('mode').value;
    $('source').value = drafts[previousMode];

    $('outputField').hidden = previousMode !== 'tac';
    $('inputBadge').textContent = previousMode.toUpperCase();

    clearResult();
    error('');
};

$('sample').onclick = () => {
    $('source').value = samples[$('mode').value];

    drafts[$('mode').value] = $('source').value;

    clearResult();
};

$('source').addEventListener('input', () => {
    if (result) {
        $('status').textContent = 'Source changed · run again';
    }
});

$('file').onchange = async e => {
    const f = e.target.files[0];

    if (!f) {
        return;
    }

    if (f.size > 20000) {
        error('File is larger than 20,000 bytes.');
        return;
    }

    $('source').value = await f.text();
    drafts[$('mode').value] = $('source').value;

    clearResult();
};

$('run').onclick = async () => {
    error('');
    lock(true);

    $('status').textContent = 'Searching';

    try {
        const payload = {
            mode: $('mode').value,
            source: $('source').value,
            outputs: $('outputs').value,
            rounds: Number($('rounds').value),
            budget: Number($('budget').value),
            beam_width: Number($('beam').value),
            seed: Number($('seed').value),
            runtime_weight: Number($('runtimeWeight').value),
            enabled: [
                ...document.querySelectorAll('#operators input:checked')
            ].map(x => x.value)
        };

        const r = await api('/api/optimize', payload);

        r.source = payload.source;
        result = r;

        render();
    } catch (e) {
        error(e.message);
        $('status').textContent = 'Error';
    } finally {
        lock(false);
    }
};

$('download').onclick = () => {
    if (!result) {
        return;
    }

    save(
        result.mode === 'python' ? 'optimized.py' : 'optimized.tac',
        result.mode === 'python'
            ? result.optimized_python
            : result.download_tac
    );
};

$('report').onclick = () => {
    if (result) {
        save(
            'optimization_report.json',
            JSON.stringify(result, null, 2),
            'application/json'
        );
    }
};

document.querySelectorAll('[data-tab]').forEach(button => {
    button.onclick = () => {
        document.querySelectorAll('[data-tab]').forEach(tab => {
            tab.classList.toggle('active', tab === button);
        });

        document.querySelectorAll('.tab-content').forEach(content => {
            content.hidden = content.id !== button.dataset.tab;
        });
    };
});

function stat(label, value) {
    return `
        <div class="stat">
            <span>${esc(label)}</span>
            <strong>${esc(value)}</strong>
        </div>
    `;
}

function lineChart(rows) {
    const w = 540;
    const h = 220;
    const p = 42;

    const max = Math.max(1, ...rows.map(x => x.best_cost));
    const end = Math.max(1, rows.at(-1).evaluations);

    const points = rows.map(x =>
        `${p + x.evaluations / end * (w - 2 * p)},` +
        `${h - p - x.best_cost / max * (h - 2 * p)}`
    ).join(' ');

    let axes = '';

    for (let n = 0; n <= 4; n++) {
        const y = h - p - n / 4 * (h - 2 * p);

        axes += `
            <line
                x1="${p}"
                y1="${y}"
                x2="${w - p}"
                y2="${y}"
                stroke="#e4eae5"
            />
            <text
                x="${p - 8}"
                y="${y + 4}"
                text-anchor="end"
            >${(max * n / 4).toFixed(1)}</text>
        `;
    }

    return `
        <svg
            class="chart"
            viewBox="0 0 ${w} ${h}"
            role="img"
            aria-label="Best score versus candidates evaluated"
        >
            ${axes}

            <polyline
                points="${points}"
                fill="none"
                stroke="#166653"
                stroke-width="3"
            />

            <text x="${p}" y="${h - 15}">0</text>

            <text
                x="${w - p}"
                y="${h - 15}"
                text-anchor="end"
            >${end} candidates</text>
        </svg>
    `;
}

function render() {
    const r = result;
    const s = r.summary;

    $('results').hidden = false;
    $('optimized').classList.remove('empty');

    $('optimized').textContent =
        r.mode === 'python'
            ? r.optimized_python
            : r.download_tac;

    $('status').textContent =
        r.validation.method === 'exact polynomial identity'
            ? 'Identity checked'
            : 'Tests passed';

    $('download').disabled = false;
    $('report').disabled = false;

    $('resultNote').textContent =
        `${s.stop_reason}. Search took ${s.search_ms} ms. ` +
        `Scoring: ${s.runtime_weight
            ? 'static + measured runtime'
            : 'static cost'}.`;

    $('stats').innerHTML =
        stat('Static cost reduction', s.cost_reduction_percent + '%') +
        stat(
            'Score · original → best',
            `${r.nodes[0].cost.toFixed(2)} → ` +
            `${r.nodes[r.selected_id].cost.toFixed(2)}`
        ) +
        stat('Candidates evaluated', s.candidates) +
        stat('Rounds completed', s.rounds) +
        stat('Final input checks', r.validation.independent_cases);

    $('costChart').innerHTML = lineChart(r.history);

    $('metricChart').innerHTML =
        '<div class="legend">' +
        '<span><i class="original"></i>Original</span>' +
        '<span><i class="selected"></i>Selected</span>' +
        '</div>' +
        ['instructions', 'arithmetic', 'temporaries'].map(k => {
            const a = r.original_metrics[k];
            const b = r.optimized_metrics[k];
            const m = Math.max(1, a, b);

            return `
                <div class="bar-row">
                    ${esc(k)}

                    <div class="bar-pair">
                        <div
                            class="bar original"
                            style="width:${a / m * 80}%"
                        ></div>
                        ${a}
                    </div>

                    <div class="bar-pair">
                        <div
                            class="bar selected"
                            style="width:${b / m * 80}%"
                        ></div>
                        ${b}
                    </div>
                </div>
            `;
        }).join('');

    const t = r.timing;

    $('timing').innerHTML = t
        ? `
            <div class="timing-values">
                <div>
                    <small>Original</small>
                    <strong>${t.original.median_us} µs</strong>
                </div>

                <div>
                    <small>Selected</small>
                    <strong>${t.selected.median_us} µs</strong>
                </div>
            </div>

            <p>${esc(t.conclusion)}</p>

            <p class="hint">
                Observed ratio: ${t.speedup}×.
                Original range: ${t.original.min_us}–${t.original.max_us} µs.
                Selected range: ${t.selected.min_us}–${t.selected.max_us} µs.
            </p>

            <p class="hint">
                ${esc(t.label)}.
                This does not measure native Python or machine-code speedup.
            </p>
        `
        : 'Timing disabled.';

    $('baselines').innerHTML =
        '<table>' +
        '<thead>' +
        '<tr><th>Method</th><th>Static cost</th><th>Checked</th></tr>' +
        '</thead>' +
        '<tbody>' +
        r.baselines.map(b => `
            <tr>
                <td>${esc(b.name)}</td>
                <td>${b.metrics.static_cost}</td>
                <td>${b.valid ? 'PASS' : 'FAIL'}</td>
            </tr>
        `).join('') +
        `
            <tr>
                <td>Mutation search</td>
                <td>${r.optimized_metrics.static_cost}</td>
                <td>PASS</td>
            </tr>
        ` +
        '</tbody></table>';

    $('originalTAC').textContent = r.original_tac;
    $('selectedTAC').textContent = r.optimized_tac;

    $('validationDetails').innerHTML = `
        <p><strong>${esc(r.validation.method)}</strong></p>

        <p>
            Each candidate: ${r.validation.search_cases} input cases.<br>
            Selected candidate: ${r.validation.independent_cases} final cases,
            using a separate random seed.
        </p>

        <p>${esc(r.validation.scope)}</p>

        <p>
            Finite tests alone are not a proof. Polynomial normalization can
            establish output identity for this restricted arithmetic; it is
            not a proof for arbitrary Python.
        </p>

        <p>
            Validity rate:
            ${s.validity_rate === null
                ? 'N/A (no candidates)'
                : s.validity_rate + '%'}
            of distinct changed candidates.
            Duplicate/no-change attempts skipped: ${s.duplicates_skipped}.
        </p>
    `;

    $('example').textContent = JSON.stringify(r.example, null, 2);

    $('counterexamples').textContent =
        r.validation.counterexamples.length
            ? JSON.stringify(r.validation.counterexamples, null, 2)
            : 'No failing inputs were found. Counterexamples are retained ' +
              'and tested first for later candidates in the same run.';

    $('path').innerHTML = r.winning_path.map((id, i) => `
        ${i ? '<span>→</span>' : ''}
        <button data-node="${id}">
            #${id} ${esc(r.nodes[id].operator)}<br>
            ${r.nodes[id].cost.toFixed(2)}
        </button>
    `).join('');

    $('path').querySelectorAll('button').forEach(button => {
        button.onclick = () => showNode(Number(button.dataset.node));
    });

    renderCandidates();
    showNode(r.selected_id);
}

function renderCandidates() {
    if (!result) {
        return;
    }

    const term = $('filter').value.toLowerCase();

    $('candidates').innerHTML = result.nodes
        .filter(n =>
            (n.id + ' ' + n.operator).toLowerCase().includes(term)
        )
        .map(n => `
            <tr
                data-id="${n.id}"
                class="${n.id === result.selected_id ? 'chosen' : ''}"
            >
                <td>
                    #${n.id} /
                    ${n.parent === null ? '—' : '#' + n.parent}
                </td>
                <td>${n.round}</td>
                <td>${esc(n.operator)}</td>
                <td>${n.cost === null ? '—' : n.cost.toFixed(2)}</td>
                <td>${n.valid ? 'PASS' : 'REJECT'}</td>
            </tr>
        `).join('');

    $('candidates').querySelectorAll('tr').forEach(row => {
        row.onclick = () => showNode(Number(row.dataset.id));
    });
}

$('filter').oninput = renderCandidates;

function showNode(id) {
    const n = result.nodes[id];

    $('candidateTitle').textContent =
        `Candidate #${id}${id === result.selected_id ? ' · selected' : ''}`;

    $('candidateReason').textContent =
        (n.reason || 'Original program, before search.') +
        ' Validation: ' + n.method + '.';

    $('branches').innerHTML =
        (n.parent !== null
            ? `<button data-branch="${n.parent}">← Parent #${n.parent}</button>`
            : '') +
        result.nodes
            .filter(x => x.parent === id)
            .map(x => `
                <button data-branch="${x.id}">
                    #${x.id} ${esc(x.operator)} →
                </button>
            `)
            .join('');

    $('branches').querySelectorAll('button').forEach(button => {
        button.onclick = () => showNode(Number(button.dataset.branch));
    });

    $('candidateCode').textContent = n.code;

    $('diff').innerHTML = n.changes
        ? n.changes
            .split('\n')
            .map(line => `
                <span class="${
                    line.startsWith('+')
                        ? 'add'
                        : line.startsWith('-')
                            ? 'remove'
                            : ''
                }">${esc(line)}</span>
            `)
            .join('\n')
        : 'No parent: this is the reference program.';
}

$('benchmark').onclick = async () => {
    error('');
    lock(true);

    $('busy').textContent = 'Benchmark running. Progress appears below.';
    $('progress').hidden = false;
    $('progress').value = 0;

    try {
        const data = await api('/api/benchmark', {
            programs: Number($('programs').value)
        });

        let job;

        do {
            await new Promise(resolve => setTimeout(resolve, 500));

            job = await api('/api/job/' + data.job);

            $('progress').max = job.total;
            $('progress').value = job.done;

            $('benchStatus').textContent =
                `${job.done} / ${job.total} programs`;

        } while (job.status === 'running');

        if (job.status === 'error') {
            throw new Error(job.error);
        }

        bench = job.result;

        $('benchDownload').disabled = false;
        $('benchCSV').disabled = false;

        const s = bench.summary;

        $('benchSummary').innerHTML = `
            <div class="stats">
                ${stat('Programs checked', s.passed_programs + '/' + s.programs)}
                ${stat('Exact identities', s.exact_identity_programs)}
                ${stat('Average static reduction', s.average_static_reduction_percent + '%')}
                ${stat('Search wins vs repeated', s.search_beats_repeated)}
                ${stat('Ties / losses', s.search_ties_repeated + ' / ' + s.search_loses_repeated)}
            </div>

            <p class="hint">
                ${esc(s.note)}
                Average search time: ${s.average_search_ms} ms;
                average rounds: ${s.average_depth};
                average candidate validity: ${s.average_validity_percent}%.
            </p>
        `;

        $('benchStatus').textContent = 'Benchmark complete.';

    } catch (e) {
        error(e.message);
        $('benchStatus').textContent = 'Benchmark failed.';

    } finally {
        lock(false);
        $('busy').textContent = 'Evaluating candidates…';
    }
};

$('benchDownload').onclick = () => {
    if (bench) {
        save(
            'benchmark.json',
            JSON.stringify(bench, null, 2),
            'application/json'
        );
    }
};

$('benchCSV').onclick = () => {
    if (!bench || !bench.rows.length) {
        return;
    }

    const keys = Object.keys(bench.rows[0]);

    const cell = value =>
        '"' + String(value ?? '').replaceAll('"', '""') + '"';

    save(
        'benchmark.csv',
        [
            keys.map(cell).join(','),
            ...bench.rows.map(row =>
                keys.map(key => cell(row[key])).join(',')
            )
        ].join('\r\n'),
        'text/csv'
    );
};

api('/api/operators')
    .then(ops => {
        $('operators').innerHTML = ops.map(o => `
            <label title="${esc(o.description)}">
                <input
                    type="checkbox"
                    value="${o.id}"
                    ${o.default ? 'checked' : ''}
                >
                ${esc(o.name)}
            </label>
        `).join('');
    })
    .catch(e => error(e.message));
