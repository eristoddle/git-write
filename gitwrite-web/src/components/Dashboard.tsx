import React from 'react';
import { Button } from './ui/button';
import ThemeToggle from './ThemeToggle';

const Dashboard: React.FC = () => {
  return (
    <div className="flex flex-col items-center space-y-4">
      <div className="absolute top-4 right-4">
         <ThemeToggle />
      </div>
      <h2 className="text-3xl font-bold">Dashboard</h2>
      <p>Welcome to your dashboard!</p>
      <Button>Click me</Button>
    </div>
  );
};

export default Dashboard;
