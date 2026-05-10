import React from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import {
  Upload, FolderOpen, Mic, Network,
  BrainCircuit, Sparkles, ArrowRight, Search, FileText,
} from 'lucide-react';
import { Button } from '../components/ui/button';

const FEATURES = [
  {
    id: 'upload',
    icon: Upload,
    title: 'OCR Upload',
    description: 'Photograph handwritten notes — AI extracts text in seconds with 90%+ accuracy. Supports Hindi and English.',
    iconBg: 'bg-blue-50',
    iconColor: 'text-blue-600',
    cardBg: 'from-blue-500/8 to-transparent',
    border: 'border-blue-100',
    ctaColor: 'text-blue-600',
    route: '/upload',
    cta: 'Upload Notes',
    span: 'sm:col-span-2',
  },
  {
    id: 'voice',
    icon: Mic,
    title: 'Voice Linking',
    description: 'Transcribe lectures and auto-link them to your written notes by semantic similarity.',
    iconBg: 'bg-orange-50',
    iconColor: 'text-orange-500',
    cardBg: 'from-orange-500/8 to-transparent',
    border: 'border-orange-100',
    ctaColor: 'text-orange-500',
    route: '/voice',
    cta: 'Open Voice',
    span: 'sm:col-span-1',
  },
  {
    id: 'graph',
    icon: Network,
    title: 'Knowledge Graph',
    description: 'See how your notes connect as an interactive force-directed knowledge map.',
    iconBg: 'bg-purple-50',
    iconColor: 'text-purple-600',
    cardBg: 'from-purple-500/8 to-transparent',
    border: 'border-purple-100',
    ctaColor: 'text-purple-600',
    route: '/graph',
    cta: 'Open Graph',
    span: 'sm:col-span-1',
  },
  {
    id: 'rag',
    icon: BrainCircuit,
    title: 'Ask Your Notes',
    description: 'Ask any question — the AI retrieves relevant passages from your notes and synthesises a cited answer.',
    iconBg: 'bg-violet-50',
    iconColor: 'text-violet-600',
    cardBg: 'from-violet-500/8 to-transparent',
    border: 'border-violet-100',
    ctaColor: 'text-violet-600',
    route: '/library',
    cta: 'Open Library',
    span: 'sm:col-span-2',
  },
];

const containerVariants = {
  hidden: {},
  show: { transition: { staggerChildren: 0.08 } },
};
const itemVariants = {
  hidden: { opacity: 0, y: 18 },
  show: { opacity: 1, y: 0, transition: { duration: 0.38, ease: 'easeOut' } },
};

export const Dashboard = () => {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-background">
      {/* Header — glassmorphism */}
      <header className="sticky top-0 z-50 w-full border-b backdrop-blur-xl bg-background/80">
        <div className="container flex h-16 items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="p-1.5 rounded-lg bg-primary/10">
              <Sparkles className="w-5 h-5 text-primary" />
            </div>
            <span className="text-xl font-semibold tracking-tight">ScribeAI</span>
          </div>

          <nav className="flex items-center gap-1">
            <Button variant="ghost" size="sm" onClick={() => navigate('/voice')} data-testid="voice-nav-btn">
              <Mic className="w-4 h-4 mr-1.5" />
              Voice
            </Button>
            <Button variant="ghost" size="sm" onClick={() => navigate('/graph')} data-testid="graph-nav-btn">
              <Network className="w-4 h-4 mr-1.5" />
              Graph
            </Button>
            <Button variant="ghost" size="sm" onClick={() => navigate('/library')} data-testid="library-nav-btn">
              <FolderOpen className="w-4 h-4 mr-1.5" />
              Library
            </Button>
          </nav>
        </div>
      </header>

      <main className="container py-14 md:py-20 max-w-5xl mx-auto px-4">
        {/* Hero */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.45 }}
          className="text-center space-y-5 mb-14"
        >
          <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-primary/10 text-primary text-sm font-medium">
            <Sparkles className="w-3.5 h-3.5" />
            AI-Powered Study Assistant
          </span>

          <h1 className="text-4xl md:text-5xl font-semibold tracking-tight leading-tight">
            Transform Handwritten Notes
            <br />
            <span className="text-primary">Into Digital Knowledge</span>
          </h1>

          <p className="text-lg leading-relaxed text-muted-foreground max-w-xl mx-auto">
            Upload, transcribe, connect and query your handwritten notes with AI — in Hindi and English.
          </p>

          <div className="flex flex-col sm:flex-row gap-3 justify-center pt-1">
            <Button size="lg" onClick={() => navigate('/upload')} className="shadow-sm" data-testid="upload-cta-btn">
              <Upload className="w-4 h-4 mr-2" />
              Upload Notes
            </Button>
            <Button size="lg" variant="outline" onClick={() => navigate('/library')} data-testid="view-library-btn">
              <Search className="w-4 h-4 mr-2" />
              View Library
            </Button>
          </div>
        </motion.div>

        {/* Bento Feature Grid */}
        <motion.div
          variants={containerVariants}
          initial="hidden"
          animate="show"
          className="grid grid-cols-1 sm:grid-cols-3 gap-4"
        >
          {FEATURES.map((f) => {
            const Icon = f.icon;
            return (
              <motion.div
                key={f.id}
                variants={itemVariants}
                onClick={() => navigate(f.route)}
                className={`
                  group relative overflow-hidden rounded-2xl border ${f.border} ${f.span}
                  bg-gradient-to-br ${f.cardBg} bg-card p-6
                  cursor-pointer select-none
                  hover:-translate-y-1 hover:shadow-[0_8px_28px_rgba(0,0,0,0.07)]
                  transition-all duration-300
                `}
              >
                <div className={`inline-flex p-2.5 rounded-xl ${f.iconBg} mb-4`}>
                  <Icon className={`w-5 h-5 ${f.iconColor}`} strokeWidth={1.75} />
                </div>

                <h3 className="text-base font-semibold mb-1.5">{f.title}</h3>
                <p className="text-sm text-muted-foreground leading-relaxed mb-5">
                  {f.description}
                </p>

                <span className={`inline-flex items-center gap-1.5 text-sm font-medium ${f.ctaColor} group-hover:gap-2.5 transition-all duration-200`}>
                  {f.cta}
                  <ArrowRight className="w-3.5 h-3.5" />
                </span>
              </motion.div>
            );
          })}
        </motion.div>

        {/* Bottom hint */}
        <motion.p
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.7, duration: 0.5 }}
          className="text-center text-sm text-muted-foreground mt-10 flex items-center justify-center gap-1.5"
        >
          <FileText className="w-3.5 h-3.5" />
          Use the RAG sidebar (bottom-right) to ask questions about your notes at any time
        </motion.p>
      </main>
    </div>
  );
};

export default Dashboard;
