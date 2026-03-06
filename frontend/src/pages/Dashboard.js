import React from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Upload, FolderOpen, Search, FileText, Sparkles } from 'lucide-react';
import { Button } from '../components/ui/button';

export const Dashboard = () => {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="sticky top-0 z-50 w-full border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
        <div className="container flex h-16 items-center justify-between">
          <div className="flex items-center gap-2">
            <Sparkles className="w-6 h-6 text-primary" />
            <h1 className="text-2xl font-semibold tracking-tight">ScribeAI</h1>
          </div>
          <nav className="flex items-center gap-4">
            <Button
              variant="ghost"
              onClick={() => navigate('/library')}
              data-testid="library-nav-btn"
            >
              <FolderOpen className="w-4 h-4 mr-2" />
              Library
            </Button>
          </nav>
        </div>
      </header>

      {/* Main Content */}
      <main className="container py-12 md:py-24">
        <div className="max-w-3xl mx-auto text-center space-y-8">
          {/* Hero Section */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
            className="space-y-4"
          >
            <h2 className="text-4xl md:text-5xl font-semibold tracking-tight leading-tight">
              Transform Handwritten Notes
              <br />
              Into Digital Text
            </h2>
            <p className="text-lg leading-relaxed text-muted-foreground">
              Upload photos of your handwritten notes in Hindi and English.
              Get accurate transcriptions powered by AI with searchable PDFs.
            </p>
          </motion.div>

          {/* CTA Buttons */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.2 }}
            className="flex flex-col sm:flex-row gap-4 justify-center"
          >
            <Button
              size="lg"
              onClick={() => navigate('/upload')}
              className="shadow-sm hover:shadow-md transition-shadow"
              data-testid="upload-cta-btn"
            >
              <Upload className="w-5 h-5 mr-2" />
              Upload Notes
            </Button>
            <Button
              size="lg"
              variant="outline"
              onClick={() => navigate('/library')}
              data-testid="view-library-btn"
            >
              <Search className="w-5 h-5 mr-2" />
              View Library
            </Button>
          </motion.div>

          {/* Features Grid */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.4 }}
            className="grid grid-cols-1 sm:grid-cols-3 gap-6 mt-16"
          >
            <FeatureCard
              icon={<FileText className="w-6 h-6" />}
              title="Mixed Language"
              description="Supports Hindi (Devanagari) and English handwriting"
            />
            <FeatureCard
              icon={<Search className="w-6 h-6" />}
              title="Searchable PDFs"
              description="Generate PDFs with selectable text layer"
            />
            <FeatureCard
              icon={<FolderOpen className="w-6 h-6" />}
              title="Smart Organization"
              description="Organize notes in folders with keyword search"
            />
          </motion.div>
        </div>
      </main>
    </div>
  );
};

const FeatureCard = ({ icon, title, description }) => {
  return (
    <div className="bg-card text-card-foreground rounded-xl border border-border/50 p-6 shadow-sm hover:shadow-md transition-shadow duration-300">
      <div className="flex flex-col items-center text-center space-y-3">
        <div className="p-3 rounded-lg bg-primary/10 text-primary">
          {icon}
        </div>
        <h3 className="text-lg font-medium">{title}</h3>
        <p className="text-sm text-muted-foreground leading-relaxed">
          {description}
        </p>
      </div>
    </div>
  );
};

export default Dashboard;
