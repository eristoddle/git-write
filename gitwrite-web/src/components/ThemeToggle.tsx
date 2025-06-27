import React from "react";
import { useTheme } from "./theme-provider";
import { Button } from "./ui/button"; // Auto-generated path by Shadcn

const ThemeToggle: React.FC = () => {
  const { theme, setTheme } = useTheme();

  const toggleTheme = () => {
    setTheme(theme === "light" ? "dark" : "light");
  };

  return (
    <Button onClick={toggleTheme} variant="outline" size="icon">
      {theme === 'light' ?
        <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/></svg>
        :
        <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 3a6.364 6.364 0 0 0 0 18 6.364 6.364 0 0 0 0-18Z"/><path d="M12 9v6"/><path d="M9 12h6"/></svg>
      }
      <span className="sr-only">Toggle theme</span>
    </Button>
  );
};

export default ThemeToggle;
