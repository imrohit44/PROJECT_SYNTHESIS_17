import { SiteFooter } from "./components/SiteFooter";
import { SiteHeader } from "./components/SiteHeader";
import { DeepDiveSection } from "./sections/DeepDiveSection";
import { EvolutionSection } from "./sections/EvolutionSection";
import { HeroSection } from "./sections/HeroSection";
import { LiveAppSection } from "./sections/LiveAppSection";
import { SourceSection } from "./sections/SourceSection";
import { WhySection } from "./sections/WhySection";

/**
 * Synthesis Explorer: one page, one story.
 * Hero → the argument → the evolution engine → the zooms → the receipts →
 * the running system.
 */
export function App() {
  return (
    <div className="shell" id="top">
      <SiteHeader />
      <main className="shell__main" id="main">
        <HeroSection />
        <WhySection />
        <EvolutionSection />
        <DeepDiveSection />
        <SourceSection />
        <LiveAppSection />
      </main>
      <SiteFooter />
    </div>
  );
}
