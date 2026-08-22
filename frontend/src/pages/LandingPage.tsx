, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.4 }}
          >
            Your Personal <br className="hidden md:block" />
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-primary to-inverse-primary">
              Knowledge Engine.
            </span>
          </motion.h1>

          {/* Subheadline */}
          <motion.p
            className="font-body-lg text-body-lg text-on-surface-variant max-w-2xl mx-auto mb-10 leading-relaxed"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.5 }}
          >
            Automatically extract entities, relationships, and insights from Instagram Reels, web pages, and documents into a private, searchable knowledge graph.
          </motion.p>

          {/* CTA Buttons */}
          <motion.div
            className="flex flex-col sm:flex-row gap-4 w-full sm:w-auto"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.6 }}
          >
            <Link
              to="/analyze"
              className="bg-inverse-primary text-white font-body-md text-body-md px-8 py-3 rounded hover:bg-primary-container transition-all hover:shadow-[0_0_20px_rgba(73,75,214,0.4)] flex items-center justify-center gap-2"
            >
              Get Started for Free
              <ArrowRight size={20} />
            </Link>
            <Link
              to="/demo"
              className="border border-surface-variant bg-transparent text-on-surface hover:bg-surface-container font-body-md text-body-md px-8 py-3 rounded transition-colors flex items-center justify-center gap-2"
            >
              <Play size={20} />
              Watch Demo
            </Link>
          </motion.div>

          {/* Trust Indicators */}
          <motion.div
            className="mt-16 flex flex-wrap justify-center gap-8 opacity-50"
            initial={{ opacity: 0 }}
            animate={{ opacity: 0.5 }}
            transition={{ duration: 0.6, delay: 0.8 }}
          >
            {trustBadges.map((badge) => (
              <span key={badge} className="font-label-sm text-label-sm text-on-surface-variant uppercase tracking-wider">
                {badge}
              </span>
            ))}
          </motion.div>
        </div>
      </motion.main>

      {/* Stats Bar */}
      <motion.section
        className="bg-surface-container border-y border-surface-variant/30 py-lg"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.6, delay: 0.8 }}
        whileInView={{ opacity: 1 }}
        viewport={{ once: true }}
      >
        <div className="max-w-container-max mx-auto px-md">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-lg">
            {stats.map((stat, i) => (
              <motion.div
                key={stat.label}
                className="text-center"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.5, delay: 0.9 + i * 0.1 }}
              >
                <div className="font-h1 text-h1 text-primary mb-1">{stat.value}</div>
                <div className="font-label-sm text-label-sm text-on-surface-variant uppercase tracking-wider">{stat.label}</div>
              </motion.div>
            ))}
          </div>
        </div>
      </motion.section>

      {/* Features Bento Grid */}
      <motion.section
        className="max-w-container-max mx-auto px-md py-24 border-x border-surface-variant/30"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.6 }}
        whileInView={{ opacity: 1 }}
        viewport={{ once: true }}
      >
        <motion.div
          className="mb-12"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
        >
          <h2 className="font-h1 text-h1 text-on-surface mb-4">Architectural Superiority.</h2>
          <p className="font-body-lg text-body-lg text-on-surface-variant max-w-xl">
            Built for researchers and developers who demand absolute precision in data extraction and structural relationship mapping.
          </p>
        </motion.div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {features.map((feature, i) => (
            <motion.div
              key={feature.title}
              className="glass-panel p-8 rounded-lg relative overflow-hidden group hover:border-outline-variant transition-colors"
              initial={{ opacity: 0, y: 30 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 1 + i * 0.1 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
            >
              <div className="absolute top-0 left-0 bg-surface-container-highest px-3 py-1 font-label-sm text-label-sm text-on-surface-variant rounded-br uppercase text-[10px]">
                {feature.label}
              </div>
              <motion.div
                className="w-12 h-12 rounded bg-surface-container flex items-center justify-center mb-6 border border-surface-variant text-primary"
                whileHover={{ scale: 1.05, rotate: 3 }}
                transition={{ duration: 0.3 }}
              >
                <feature.icon size={24} />
              </motion.div>
              <h3 className="font-h2 text-h2 text-on-surface mb-3 text-xl">{feature.title}</h3>
              <p className="font-body-md text-body-md text-on-surface-variant">{feature.desc}</p>
            </motion.div>
          ))}
        </div>
      </motion.section>

      {/* Platform Support */}
      <motion.section
        className="max-w-container-max mx-auto px-md py-12 border-b border-surface-variant/30 flex flex-col items-center"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.6 }}
        whileInView={{ opacity: 1 }}
        viewport={{ once: true }}
      >
        <p className="font-label-sm text-label-sm text-on-surface-variant uppercase mb-8 text-center tracking-widest text-xs">
          Seamlessly integrates with
        </p>
        <motion.div
          className="flex flex-wrap justify-center gap-12 opacity-50 grayscale hover:grayscale-0 transition-all duration-500"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.2 }}
        >
          {integrations.map((integration) => (
            <motion.div
              key={integration.name}
              className="font-h2 text-h2 font-bold text-on-surface flex items-center gap-2 text-xl"
              whileHover={{ scale: 1.1, opacity: 1 }}
              transition={{ duration: 0.3 }}
            >
              <integration.icon size={24} />
              {integration.name}
            </motion.div>
          ))}
        </motion.div>
      </motion.section>

      {/* CTA Section */}
      <motion.section
        className="max-w-container-max mx-auto px-md py-24 flex flex-col items-center text-center"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.6 }}
        whileInView={{ opacity: 1 }}
        viewport={{ once: true }}
      >
        <motion.div
          className="relative p-12 w-full max-w-3xl border border-surface-variant bg-surface-container-lowest rounded-xl overflow-hidden shadow-2xl"
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
        >
          <div className="absolute inset-0 bg-gradient-to-b from-primary/5 to-transparent pointer-events-none" />
          <h2 className="font-h1 text-h1 text-on-surface mb-6 relative z-10">
            Ready to build your second brain?
          </h2>
          <p className="font-body-lg text-body-lg text-on-surface-variant mb-10 relative z-10">
            Stop losing valuable information in the noise. Centralize your research today.
          </p>
          <Link
            to="/analyze"
            className="relative z-10 bg-inverse-primary text-white font-body-md text-body-md px-10 py-4 rounded hover:bg-primary-container transition-all hover:-translate-y-1 hover:shadow-[0_10px_20px_rgba(73,75,214,0.3)] font-bold tracking-wide"
          >
            Start Analyzing Now
          </Link>
        </motion.div>
      </motion.section>

      {/* Footer */}
      <footer className="w-full bg-surface border-t border-outline-variant">
        <div className="max-w-container-max mx-auto px-md py-16 flex flex-col md:flex-row justify-between gap-lg">
          <div className="flex flex-col gap-4">
            <Link className="font-h2 text-h2 font-bold text-primary flex items-center gap-2" href="#">
              <span className="material-symbols-outlined" data-icon="hub">hub</span>
              InstaGPT
            </Link>
            <p className="font-body-md text-body-md text-on-surface-variant">
              © 2024 InstaGPT Inc. Intelligence Manifest.
            </p>
          </div>
          <div className="flex flex-col md:flex-row gap-8 font-body-md text-body-md">
            <Link className="text-on-surface-variant hover:text-secondary transition-colors" href="#">Privacy Policy</Link>
            <Link className="text-on-surface-variant hover:text-secondary transition-colors" href="#">Terms of Service</Link>
            <Link className="text-on-surface-variant hover:text-secondary transition-colors" href="#">API Documentation</Link>
            <Link className="text-on-surface-variant hover:text-secondary transition-colors" href="#">System Status</Link>
          </div>
        </div>
      </footer>
    </div>
  )
}