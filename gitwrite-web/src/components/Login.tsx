import React, { useState } from 'react';
import { GitWriteClient } from 'gitwrite-sdk';
import { useNavigate } from 'react-router-dom';

const Login: React.FC = () => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError(null);

    const client = new GitWriteClient('http://localhost:8000'); // Assuming API is running on port 8000

    try {
      const response = await client.login({ username, password });
      if (response.access_token) {
        localStorage.setItem('jwtToken', response.access_token);
        navigate('/dashboard');
      } else {
        setError('Login failed: No access token received.');
      }
    } catch (err) {
      console.error('Login error:', err);
      setError('Login failed: Invalid username or password.');
    }
  };

  return (
    <div>
      <h2>Login</h2>
      <form onSubmit={handleSubmit}>
        <div>
          <label htmlFor="username">Username:</label>
          <input
            type="text"
            id="username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
          />
        </div>
        <div>
          <label htmlFor="password">Password:</label>
          <input
            type="password"
            id="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </div>
        <button type="submit">Login</button>
      </form>
      {error && <p style={{ color: 'red' }}>{error}</p>}
    </div>
  );
};

export default Login;
