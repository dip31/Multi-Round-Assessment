export default function TestPage() {
  return (
    <div style={{ padding: '20px', fontFamily: 'Arial' }}>
      <h1 style={{ color: 'green' }}>✅ Frontend is Working!</h1>
      <p>If you can see this page, your Next.js frontend is running correctly.</p>
      <ul>
        <li>Server: Running on port 3000</li>
        <li>Next.js: Version 16.1.6</li>
        <li>Status: Operational</li>
      </ul>
      <hr />
      <h2>Next Steps:</h2>
      <ol>
        <li>Go back to <a href="/login" style={{ color: 'blue' }}>/login</a></li>
        <li>If login page is blank, check browser console (F12)</li>
        <li>Try hard refresh (Ctrl + Shift + R)</li>
      </ol>
    </div>
  );
}
