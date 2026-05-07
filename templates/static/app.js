async function analyzeText(){

const text = document.getElementById("inputText").value;

const formData = new FormData();

formData.append("input_type","text");
formData.append("text",text);

const response = await fetch("/analyze",{
method:"POST",
body:formData
});

const data = await response.json();

document.getElementById("result").innerHTML = `

<div class="card">
<div class="level">${data.lesson_level}</div>
<h3>課文</h3>
<p>${data.text}</p>
</div>

<div class="card">
<h3>對話</h3>
<p>${data.dialogue}</p>
</div>

<div class="card">
<h3>生詞</h3>
${data.new_words.map(v=>`
<p>${v.word}（${v.level}）</p>
`).join("")}
</div>

<div class="card">
<h3>語法</h3>
${data.grammar.map(g=>`
<p>${g.name}（${g.level}）</p>
`).join("")}
</div>

<div class="card">
<h3>閱讀</h3>
<p>${data.reading}</p>
</div>

<div class="card">
<h3>任務</h3>
${data.tasks.map(t=>`
<p>${t}</p>
`).join("")}
</div>

<div class="card">
<h3>練習</h3>
${data.exercises.map(e=>`
<p>${e.question}</p>
`).join("")}
</div>

<div class="card">
<h3>備課筆記</h3>
<p>${data.notes}</p>
</div>

`;

}
