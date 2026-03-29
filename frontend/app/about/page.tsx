import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "About | Bizkaia Connectivity",
  description:
    "Methodology, data sources, and limitations of the Bizkaia transport connectivity tool.",
};

const COLOR_STOPS = [
  "#1a0a00", "#7f1b00", "#c4321a", "#e05a2b", "#f0892e", "#f5b731",
  "#e8d534", "#b5d935", "#6ec440", "#2da84e", "#1a8a5c", "#0e5e8c",
];

export default function AboutPage() {
  return (
    <div className="max-w-2xl p-6 lg:p-8">
      <h1 className="text-lg font-semibold">About</h1>
      <p className="mt-1 text-sm text-muted-foreground">
        An open-source transport accessibility tool for Bizkaia, inspired by the
        UK DfT&apos;s Connectivity Assessment Toolkit.
      </p>

      <article className="mt-8 space-y-10 text-sm leading-relaxed text-muted-foreground">
        {/* What */}
        <section>
          <h2 className="mb-3 text-sm font-medium text-foreground">
            What is this tool?
          </h2>
          <p>
            Bizkaia Connectivity measures how easy it is for people in any part
            of Bizkaia to reach essential everyday services &mdash; jobs,
            schools, healthcare, and food shops &mdash; by walking or using
            public transport.
          </p>
          <p className="mt-3">
            The territory is divided into a multi-resolution square grid. Scores
            are computed at 500&nbsp;m and aggregated upwards. The map switches
            between three tiers as you zoom:
          </p>
          <ul className="mt-2 ml-4 list-disc space-y-1">
            <li><strong className="text-foreground">1&nbsp;km</strong> &mdash; regional overview</li>
            <li><strong className="text-foreground">500&nbsp;m</strong> &mdash; neighbourhood level</li>
            <li><strong className="text-foreground">100&nbsp;m</strong> &mdash; street-level detail</li>
          </ul>
          <p className="mt-3">
            Scores reflect the number and proximity of reachable destinations,
            with closer destinations weighted more heavily and diminishing
            returns for additional facilities. All scores are normalised to
            a <strong className="text-foreground">0&ndash;100</strong> scale.
          </p>
        </section>

        {/* Modes */}
        <section>
          <h2 className="mb-3 text-sm font-medium text-foreground">
            Travel modes
          </h2>
          <ul className="ml-4 list-disc space-y-2">
            <li>
              <strong className="text-foreground">Walking</strong> &mdash;
              door-to-door on the pedestrian network from OpenStreetMap.
            </li>
            <li>
              <strong className="text-foreground">Public transport</strong> &mdash;
              walk + transit using GTFS timetables for Bizkaibus, Bilbobus,
              Metro Bilbao, Euskotren, Renfe Cercan&iacute;as, and the Artxanda
              Funicular. Morning peak (07:00&ndash;10:00).
            </li>
          </ul>
          <p className="mt-3">
            Maximum travel time: <strong className="text-foreground">60 minutes</strong>.
            Destinations beyond this are considered unreachable.
          </p>
        </section>

        {/* Destinations */}
        <section>
          <h2 className="mb-3 text-sm font-medium text-foreground">
            Destination categories
          </h2>
          <div className="overflow-x-auto rounded-md border">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-muted/40">
                  <th className="px-3 py-2 text-left font-medium text-foreground">Purpose</th>
                  <th className="px-3 py-2 text-left font-medium text-foreground">Includes</th>
                  <th className="px-3 py-2 text-left font-medium text-foreground">Rationale</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                <tr>
                  <td className="px-3 py-2 font-medium text-foreground">Jobs</td>
                  <td className="px-3 py-2">Employment centres, weighted by job count</td>
                  <td className="px-3 py-2">Primary driver of economic opportunity</td>
                </tr>
                <tr>
                  <td className="px-3 py-2 font-medium text-foreground">Education</td>
                  <td className="px-3 py-2">Primary schools</td>
                  <td className="px-3 py-2">Families need reliable school access</td>
                </tr>
                <tr>
                  <td className="px-3 py-2 font-medium text-foreground">Health</td>
                  <td className="px-3 py-2">GP surgeries, healthcare centres</td>
                  <td className="px-3 py-2">Routine healthcare without a car</td>
                </tr>
                <tr>
                  <td className="px-3 py-2 font-medium text-foreground">Retail</td>
                  <td className="px-3 py-2">Supermarkets</td>
                  <td className="px-3 py-2">Basic food access</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        {/* Methodology */}
        <section>
          <h2 className="mb-3 text-sm font-medium text-foreground">
            How scores are calculated
          </h2>
          <p>
            We ask: <em>&ldquo;From this cell, how many destinations can I
            reach, how quickly, and how much does each one matter?&rdquo;</em>
          </p>

          <h3 className="mt-5 mb-2 text-sm font-medium text-foreground">
            1. Travel time computation
          </h3>
          <p>
            The R5 routing engine (via{" "}
            <code className="rounded bg-muted px-1 py-0.5 text-xs">r5r</code>)
            computes travel times from every grid cell to every destination for
            both modes. Transit calculations model transfers, waiting times, and
            walk access/egress.
          </p>

          <h3 className="mt-5 mb-2 text-sm font-medium text-foreground">
            2. Distance decay
          </h3>
          <p>
            Closer destinations count more. We apply an exponential decay:
          </p>
          <div className="my-3 rounded-md border bg-muted/30 px-4 py-2.5 text-center font-mono text-xs">
            impedance = e<sup>&minus;&alpha; &times; t</sup>
          </div>
          <p>
            where <em>t</em> is travel time in minutes and <em>&alpha;</em> is a
            mode/purpose-specific decay rate:
          </p>
          <div className="mt-2 overflow-x-auto rounded-md border">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-muted/40">
                  <th className="px-3 py-2 text-left font-medium text-foreground">Purpose</th>
                  <th className="px-3 py-2 text-left font-medium text-foreground">Walk &alpha;</th>
                  <th className="px-3 py-2 text-left font-medium text-foreground">Transit &alpha;</th>
                </tr>
              </thead>
              <tbody className="divide-y font-mono">
                <tr><td className="px-3 py-2 font-sans font-medium text-foreground">Jobs</td><td className="px-3 py-2">0.08</td><td className="px-3 py-2">0.03</td></tr>
                <tr><td className="px-3 py-2 font-sans font-medium text-foreground">Education</td><td className="px-3 py-2">0.06</td><td className="px-3 py-2">0.025</td></tr>
                <tr><td className="px-3 py-2 font-sans font-medium text-foreground">Health</td><td className="px-3 py-2">0.05</td><td className="px-3 py-2">0.02</td></tr>
                <tr><td className="px-3 py-2 font-sans font-medium text-foreground">Retail</td><td className="px-3 py-2">0.07</td><td className="px-3 py-2">0.03</td></tr>
              </tbody>
            </table>
          </div>

          <h3 className="mt-5 mb-2 text-sm font-medium text-foreground">
            3. Diminishing returns
          </h3>
          <p>
            A concave power transform compresses high values so areas with many
            destinations don&rsquo;t dominate disproportionately:
          </p>
          <div className="my-3 rounded-md border bg-muted/30 px-4 py-2.5 text-center font-mono text-xs">
            adjusted = raw<sup>0.7</sup>
          </div>

          <h3 className="mt-5 mb-2 text-sm font-medium text-foreground">
            4. Normalisation
          </h3>
          <p>
            Each (mode, purpose) pair is scaled to 0&ndash;100 via min-max
            normalisation across all cells.
          </p>

          <h3 className="mt-5 mb-2 text-sm font-medium text-foreground">
            5. Combined score
          </h3>
          <p>
            A weighted average of all eight normalised scores:
          </p>
          <div className="mt-2 overflow-x-auto rounded-md border">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-muted/40">
                  <th className="px-3 py-2 text-left font-medium text-foreground">Purpose</th>
                  <th className="px-3 py-2 text-left font-medium text-foreground">Walk</th>
                  <th className="px-3 py-2 text-left font-medium text-foreground">Transit</th>
                </tr>
              </thead>
              <tbody className="divide-y font-mono">
                <tr><td className="px-3 py-2 font-sans font-medium text-foreground">Jobs</td><td className="px-3 py-2">15%</td><td className="px-3 py-2">15%</td></tr>
                <tr><td className="px-3 py-2 font-sans font-medium text-foreground">Education</td><td className="px-3 py-2">10%</td><td className="px-3 py-2">10%</td></tr>
                <tr><td className="px-3 py-2 font-sans font-medium text-foreground">Health</td><td className="px-3 py-2">12.5%</td><td className="px-3 py-2">12.5%</td></tr>
                <tr><td className="px-3 py-2 font-sans font-medium text-foreground">Retail</td><td className="px-3 py-2">12.5%</td><td className="px-3 py-2">12.5%</td></tr>
              </tbody>
            </table>
          </div>
          <p className="mt-3">
            Jobs receive the largest share. The combined score is normalised a
            final time to 0&ndash;100.
          </p>
        </section>

        {/* Reading the map */}
        <section>
          <h2 className="mb-3 text-sm font-medium text-foreground">
            Reading the map
          </h2>
          <p>Each cell is coloured by its score:</p>
          <div className="mt-3">
            <div
              className="h-3 w-full rounded-sm"
              style={{
                background: `linear-gradient(to right, ${COLOR_STOPS.join(", ")})`,
              }}
            />
            <div className="mt-1 flex justify-between text-xs">
              <span>0</span>
              <span>50</span>
              <span>100</span>
            </div>
          </div>
          <p className="mt-3">
            Use the layer panel to switch between combined and per-purpose
            scores. Click a cell for its breakdown. Toggle transit routes and
            stops to see the underlying network.
          </p>
        </section>

        {/* Data sources */}
        <section>
          <h2 className="mb-3 text-sm font-medium text-foreground">
            Data sources
          </h2>
          <ul className="ml-4 list-disc space-y-1">
            <li><strong className="text-foreground">Network</strong> &mdash; OpenStreetMap</li>
            <li><strong className="text-foreground">Transit</strong> &mdash; GTFS feeds (Bizkaibus, Bilbobus, Metro Bilbao, Euskotren, Renfe, Funicular)</li>
            <li><strong className="text-foreground">Destinations</strong> &mdash; public registers and open data portals</li>
            <li><strong className="text-foreground">Boundaries</strong> &mdash; official administrative boundaries</li>
          </ul>
        </section>

        {/* Limitations */}
        <section>
          <h2 className="mb-3 text-sm font-medium text-foreground">
            Limitations
          </h2>
          <ul className="ml-4 list-disc space-y-2">
            <li>
              <strong className="text-foreground">Modes.</strong> Only walking
              and transit. Areas well-connected by car but poorly by transit
              show low scores.
            </li>
            <li>
              <strong className="text-foreground">Timetables.</strong> Based on
              published schedules; real-world delays not captured.
            </li>
            <li>
              <strong className="text-foreground">Completeness.</strong> Some
              facilities may be missing from the destination dataset.
            </li>
            <li>
              <strong className="text-foreground">Time of day.</strong> AM peak
              only (07:00&ndash;10:00). Evening and weekend connectivity may
              differ.
            </li>
            <li>
              <strong className="text-foreground">Parameters.</strong> Decay
              rates, exponent, and weights are evidence-informed but involve
              judgement.
            </li>
            <li>
              <strong className="text-foreground">Resolution.</strong> Grid
              cells smooth local variation. Coarser tiers use
              population-weighted averages.
            </li>
          </ul>
        </section>

        {/* Open source */}
        <section>
          <h2 className="mb-3 text-sm font-medium text-foreground">
            Open source
          </h2>
          <p>
            The full scoring pipeline, API, and frontend are publicly available.
            Every step can be inspected, reproduced, and improved.
          </p>
        </section>
      </article>
    </div>
  );
}
