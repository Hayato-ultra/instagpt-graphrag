import { motion } from 'framer-motion'
import { Link } from 'react-router-dom'
import { Users, Target, Shield, Zap, Award, Globe, Lightbulb, BookOpen } from 'lucide-react'

const values = [
  { icon: Target, title: 'Precision First', desc: 'Every entity extracted, every relationship mapped with surgical accuracy. No hallucinations, only verified knowledge.' },
  { icon: Shield, title: 'Privacy by Design', desc: 'Your knowledge graph is yours alone. End-to-end encryption, zero data sharing, full data sovereignty.' },
  { icon: Zap, title: 'Developer Experience', desc: 'Built by developers, for developers. Clean APIs, comprehensive docs, and intuitive interfaces that just work.' },
  { icon: Award, title: 'Continuous Innovation', desc: 'Weekly model updates, cutting-edge research integration, and a commitment to pushing the boundaries of GraphRAG.' },
]

const team = [
  { name: 'Dr. Sarah Chen', role: 'CEO & Co-founder', bio: 'Former Google Research, PhD in Knowledge Graphs', initials: 'SC' },
  { name: 'Marcus Webb', role: 'CTO & Co-founder', bio: 'Ex-Meta Graph Infrastructure, Distributed Systems Expert', initials: 'MW' },
  { name: 'Priya Patel', role: 'VP Engineering', bio: 'Led AI Platform at Stripe, ML Systems at Scale', initials: 'PP' },
  { name: 'Dr. James Liu', role: 'Chief Scientist', bio: 'Published 40+ papers on Graph Neural Networks', initials: 'JL' },
]

const milestones = [
  { year: '2023', title: 'Founded', desc: 'Started with a vision to democratize knowledge graphs' },
  { year: '2023', title: 'Seed Round', desc: 'Raised $5M from top VCs including Sequoia' },
  { year: '2024', title: 'v1.0 Launch', desc: 'Released first public version with 10K beta users' },
  { year: '2024', title: 'v2.0 Pipeline', desc: 'Automated enrichment, semantic search, multi-modal support' },
  { year: '2025', title: 'Enterprise', desc: 'SOC 2, GDPR compliance, enterprise deployments' },
]

export default function AboutPage() {
  return (
    <div className="min-h-screen bg-background">
      {/* Navigation */}
      <nav className="fixed top-0 w-full z-50 bg-surface-container/80 backdrop-blur-md border-b border-outline-variant/10">
        <div className="flex justify-between items-center max-w-container-max mx-auto px-md h-20">
          <Link to="/" className="font-h1 text-h1 text-primary flex items-center gap-2">
            <span className="material-symbols-outlined" data-icon="hub">hub</span>
            InstaGPT
          </Link>
          <div className="hidden md:flex items-center gap-8 font-body-md text-body-md">
            <Link className="text-on-surface-variant hover:text-primary transition-colors" to="/">Home</Link>
            <Link className="text-primary font-bold" to="/about">About</Link>
            <Link className="text-on-surface-variant hover:text-primary transition-colors" to="/services">Services</Link>
            <Link className="text-on-surface-variant hover:text-primary transition-colors" to="/blog">Blog</Link>
          </div>
          <Link to="/analyze" className="bg-inverse-primary hover:bg-primary-container text-white px-6 py-2 rounded font-body-md transition-all">
            Get Started
          </Link>
        </div>
      </nav>

      <main className="pt-32">
        {/* Hero */}
        <motion.section
          className="relative max-w-container-max mx-auto px-md py-24 border-x border-surface-variant/30 text-center"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
        >
          <motion.div
            className="inline-flex items-center gap-2 px-3 py-1 mb-6 rounded-full border border-surface-variant bg-surface-container-low text-on-surface-variant font-label-sm uppercase tracking-wider"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.2 }}
          >
            <span className="w-2 h-2 rounded-full bg-secondary animate-pulse" />
            Our Mission
          </motion.div>

          <motion.h1
            className="font-display text-display md:text-display text-on-surface mb-6 max-w-3xl mx-auto"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.3 }}
          >
            Making the world&apos;s information <br />
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-primary to-inverse-primary">
              computable and connected.
            </span>
          </motion.h1>

          <motion.p
            className="font-body-lg text-body-lg text-on-surface-variant max-w-2xl mx-auto"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.4 }}
          >
            We believe knowledge shouldn&apos;t be trapped in silos. InstaGPT transforms unstructured content into interconnected intelligence — so you can find, understand, and act on what matters.
          </motion.p>
        </motion.section>

        {/* Values */}
        <motion.section
          className="max-w-container-max mx-auto px-md py-24"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.6 }}
          whileInView={{ opacity: 1 }}
          viewport={{ once: true }}
        >
          <motion.div
            className="text-center mb-16"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6 }}
          >
            <span className="font-label-sm text-label-sm text-primary uppercase tracking-widest mb-4 block">Core Values</span>
            <h2 className="font-h1 text-h1 text-on-surface mb-4">Principles That Guide Us</h2>
            <p className="font-body-lg text-body-lg text-on-surface-variant max-w-xl mx-auto">
              These aren&apos;t just words on a wall — they&apos;re the lens through which every decision is made.
            </p>
          </motion.div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            {values.map((value, i) => (
              <motion.div
                key={value.title}
                className="glass-panel p-8 rounded-lg border border-surface-variant/50 hover:border-primary/30 transition-colors"
                initial={{ opacity: 0, y: 30 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.6, delay: 0.1 * i }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
              >
                <motion.div
                  className="w-12 h-12 rounded bg-primary/10 flex items-center justify-center mb-6 border border-primary/20 text-primary"
                  whileHover={{ scale: 1.1, rotate: 5 }}
                >
                  <value.icon size={24} />
                </motion.div>
                <h3 className="font-h2 text-h2 text-on-surface mb-3">{value.title}</h3>
                <p className="font-body-md text-body-md text-on-surface-variant">{value.desc}</p>
              </motion.div>
            ))}
          </div>
        </motion.section>

        {/* Team */}
        <motion.section
          className="max-w-container-max mx-auto px-md py-24 border-y border-surface-variant/30 bg-surface-container-lowest/50"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.6 }}
          whileInView={{ opacity: 1 }}
          viewport={{ once: true }}
        >
          <motion.div
            className="text-center mb-16"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6 }}
          >
            <span className="font-label-sm text-label-sm text-primary uppercase tracking-widest mb-4 block">The Team</span>
            <h2 className="font-h1 text-h1 text-on-surface mb-4">Built by Researchers & Engineers</h2>
            <p className="font-body-lg text-body-lg text-on-surface-variant max-w-xl mx-auto">
              A small, focused team with deep expertise in knowledge graphs, ML infrastructure, and developer tools.
            </p>
          </motion.div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            {team.map((member, i) => (
              <motion.div
                key={member.name}
                className="group text-center"
                initial={{ opacity: 0, y: 30 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.6, delay: 0.1 * i }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
              >
                <motion.div
                  className="w-24 h-24 rounded-full bg-surface-container mx-auto mb-4 flex items-center justify-center font-h1 text-h1 font-bold text-primary border border-outline-variant group-hover:border-primary/50 transition-colors"
                  whileHover={{ scale: 1.05 }}
                >
                  {member.initials}
                </motion.div>
                <h3 className="font-h2 text-h2 text-on-surface mb-1">{member.name}</h3>
                <p className="font-label-sm text-label-sm text-primary mb-2">{member.role}</p>
                <p className="font-body-md text-body-md text-on-surface-variant text-sm">{member.bio}</p>
              </motion.div>
            ))}
          </div>
        </motion.section>

        {/* Timeline */}
        <motion.section
          className="max-w-container-max mx-auto px-md py-24"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.6 }}
          whileInView={{ opacity: 1 }}
          viewport={{ once: true }}
        >
          <motion.div
            className="text-center mb-16"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6 }}
          >
            <span className="font-label-sm text-label-sm text-primary uppercase tracking-widest mb-4 block">Journey</span>
            <h2 className="font-h1 text-h1 text-on-surface mb-4">Our Story So Far</h2>
          </motion.div>

          <div className="relative">
            <div className="absolute left-8 md:left-[calc(50%-1px)] top-0 bottom-0 w-[2px] bg-outline-variant/30" />
            {milestones.map((milestone, i) => (
              <motion.div
                key={milestone.year}
                className="relative flex items-start gap-6 mb-12 md:flex-row md:items-center"
                initial={{ opacity: 0, x: i % 2 === 0 ? -30 : 30 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ duration: 0.6, delay: 0.1 * i }}
                whileInView={{ opacity: 1, x: 0 }}
                viewport={{ once: true }}
              >
                <div className="relative z-10 w-16 h-16 md:w-16 md:h-16 md:flex-shrink-0 md:absolute md:left-[calc(50%-48px)] flex items-center justify-center">
                  <div className="w-4 h-4 rounded-full bg-primary border-4 border-background" />
                </div>
                <div className={`flex-1 ${i % 2 === 0 ? 'md:pr-20 text-right' : 'md:pl-20 md:ml-[calc(50%+16px)]'}}">
                  <div className="layer-1 p-6 rounded-lg">
                    <div className="font-label-sm text-label-sm text-primary uppercase tracking-widest mb-2">{milestone.year}</div>
                    <h3 className="font-h2 text-h2 text-on-surface mb-2">{milestone.title}</h3>
                    <p className="font-body-md text-body-md text-on-surface-variant">{milestone.desc}</p>
                  </div>
                </div>
              </motion.div>
            ))}
          </div>
        </motion.section>

        {/* CTA */}
        <motion.section
          className="max-w-container-max mx-auto px-md py-24 text-center"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.6 }}
          whileInView={{ opacity: 1 }}
          viewport={{ once: true }}
        >
          <motion.div
            className="max-w-2xl mx-auto"
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6 }}
          >
            <h2 className="font-h1 text-h1 text-on-surface mb-6">Join Us in Building the Future of Knowledge</h2>
            <p className="font-body-lg text-body-lg text-on-surface-variant mb-8">
              We&apos;re always looking for exceptional people who share our vision. Whether you&apos;re a researcher, engineer, or designer — let&apos;s talk.
            </p>
            <div className="flex flex-col sm:flex-row gap-4 justify-center">
              <Link to="/careers" className="bg-inverse-primary text-white px-8 py-3 rounded font-body-md hover:bg-primary-container transition-all">
                View Open Roles
              </Link>
              <Link to="/contact" className="border border-surface-variant text-on-surface px-8 py-3 rounded font-body-md hover:bg-surface-container transition-colors">
                Get in Touch
              </Link>
            </div>
          </motion.div>
        </motion.section>
      </main>

      <footer className="w-full bg-surface border-t border-outline-variant py-12">
        <div className="max-w-container-max mx-auto px-md text-center">
          <p className="font-body-md text-body-md text-on-surface-variant">© 2024 InstaGPT Inc. All rights reserved.</p>
        </div>
      </footer>
    </div>
  )
}