document.getElementById('optimizeBtn').addEventListener('click', async () => {
    const resultsDiv = document.getElementById('results');
    resultsDiv.innerText = "Processing constraints...";

    // Mock data matching the models.py structure
    const payload = {
        teachers: [{ id: "t1", name: "Smith", subject: ["Math"], available_days: ["Mon", "Tue"], max_hours_per_week: 15 }],
        rooms: [{ id: "r1", capacity: 30, is_lab: false }],
        courses: [{ id: "c1", subject: "Math", required_hours: 3, requires_lab: false, allowed_teachers: ["t1"] }]
    };

    try {
        const response = await fetch('http://127.0.0.1:8000/api/optimize', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const data = await response.json();
        displayTimetable(data, resultsDiv);
    } catch (error) {
        resultsDiv.innerText = "Connection error. Ensure Uvicorn is running.";
    }
});

function displayTimetable(data, resultsDiv) {
    if (data.status === 'error') {
        resultsDiv.innerText = `Error: ${data.message}`;
        return;
    }

    if (!data.schedule || data.schedule.length === 0) {
        resultsDiv.innerText = 'No schedule found.';
        return;
    }

    // Build a timetable grid: days x periods, showing course-teacher-room
    const days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri'];
    const periods = ['1', '2', '3', '4'];
    
    // Initialize grid
    let gridHtml = '<h3>Timetable Schedule</h3>';
    gridHtml += '<table border="1" cellpadding="5" cellspacing="0"><tr><th></th>';
    periods.forEach(p => gridHtml += `<th>P${p}</th>`);
    gridHtml += '</tr>';

    days.forEach((day, dIdx) => {
        gridHtml += `<tr><th>${day}</th>`;
        periods.forEach((p, pIdx) => {
            const shifts = data.schedule.filter(s => 
                s.day === day && s.period === `Period ${pIdx + 1}`
            );
            let content = '';
            if (shifts.length > 0) {
                shifts.forEach(s => {
                    content += `<div><strong>${s.course}</strong> by ${s.teacher} in ${s.room}</div>`;
                });
            } else {
                content = '&ndash;';
            }
            gridHtml += `<td>${content}</td>`;
        });
        gridHtml += `</tr>`;
    });

    gridHtml += '</table>';
    resultsDiv.innerHTML = gridHtml;
}