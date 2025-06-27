import React from 'react';
import ThemeToggle from './ThemeToggle';
import ProjectList from './ProjectList'; // Import ProjectList

const Dashboard: React.FC = () => {
  return (
    <div className="container mx-auto p-4">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-3xl font-bold">GitWrite Dashboard</h1>
        <ThemeToggle />
      </div>
      <ProjectList />
    </div>
  );
};

export default Dashboard;
