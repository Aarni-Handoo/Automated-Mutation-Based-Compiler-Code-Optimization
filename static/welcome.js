(() => {
  const $ = id => document.getElementById(id);
  const wait = ms => new Promise(resolve => setTimeout(resolve, ms));
  const panel = document.querySelector('.mutation-window');
  async function playMutation() {
    panel.classList.add('scanning');
    $('engineState').textContent = 'SCANNING';
    $('mutationStatus').innerHTML = '<span class="spinner"></span> Scanning mutation operators…';
    await wait(850);
    $('mutationStatus').innerHTML = '<span class="spinner"></span> Applying zero-add removal…';
    $('addZero').classList.add('changed');
    await wait(600);
    $('mutationStatus').innerHTML = '<span class="spinner"></span> Applying one-multiplication removal…';
    $('mulOne').classList.add('changed');
    await wait(650);
    $('xResult').textContent = '  ✓';
    $('yResult').textContent = '  ✓';
    document.querySelectorAll('.output-line').forEach((line, i) => setTimeout(() => line.classList.add('revealed'), i * 130));
    await wait(550);
    panel.classList.remove('scanning');
    $('mutationStatus').innerHTML = '<span class="success-icon">✓</span> Preview transformations complete';
    $('verifiedBadge').textContent = 'PREVIEW';
    $('verifiedBadge').classList.add('on');
    $('resultText').textContent = 'Illustrative mutation preview complete';
    $('costChip').textContent = 'READY TO LAUNCH';
    $('engineState').textContent = 'READY';
  }
  const launch = () => { window.location.href = '/dashboard'; };
  $('skipButton').addEventListener('click', launch);
  $('launchButton').addEventListener('click', event => { event.preventDefault(); launch(); });
  document.addEventListener('keydown', event => {
    if (event.key === 'Enter' && !['BUTTON','A','TEXTAREA','INPUT'].includes(document.activeElement.tagName)) launch();
  });
  // Intro animation is illustrative only; it does not claim backend validation.
  playMutation();
})();
