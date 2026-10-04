# Bachelor Thesis Project Proposals (ISF - ENU)

**Research Group:** Institute of Smart Farming (ISF)
**Project:** Intelligent Path Planner (IPP) Extension

## Problem Statement 1: ROS 2 Middleware & Ground Control UI with OFA Field Demonstration

### Context & Motivation
The Intelligent Path Planner (IPP) is a web-based, 3D mission planning tool. To transition IPP from a static planning application into an active Ground Control Station (GCS), a robust communication layer must be established. The system must natively interface with a heterogeneous fleet of Unmanned Ground Vehicles (UGVs) and Unmanned Aerial Vehicles (UAVs) using the ROS 2 middleware, culminating in a live physical field demonstration using the Open Farming Automation (OFA) platform to prove real-world viability.

### Objectives & Tasks
The student will design and implement an asynchronous ROS 2 bridge connecting the Python/NiceGUI backend to the robotic fleet, alongside interactive frontend UI components, and prove the system's functionality in a real-world agricultural setting.

1. **Middleware Implementation:** Develop a ROS 2 node architecture that handles bidirectional communication. Robots must be able to publish their state/pose and dynamically request route assignments and task payloads from the IPP `/mission_data` topics.
2. **Interactive UI Extension:** Enhance the MapLibre GL JS frontend. When an operator clicks on an active robot's 3D marker on the map, a floating information window must appear, displaying live ROS 2 telemetry. A dynamic, thin tether line must visually connect the UI window to the moving robot on the screen to prevent clutter during multi-robot operations.
3. **Simulation & Testing Pipeline:** The implementation must initially be rigorously tested without requiring physical hardware. The student must develop dummy ROS 2 data provider nodes to simulate robot fleets. Automated unit tests and ROS 2 bag (`rosbag2`) replay scripts must be created to validate system connectivity, load handling, and UI responsiveness.
4. **OFA Field Demonstration:** Conduct a live field demonstration using the Open Farming Automation (OFA) UGV robot. This test must conclusively prove the end-to-end functionality of the system: successful dispatch of an IPP-generated coverage route, autonomous execution by the OFA robot, and stable, real-time telemetry visualization back in the planner UI.

### Recommended Literature & Resources

* **ROS 2 Architecture:** [rclpy Documentation](https://docs.ros.org/en/rolling/p/rclpy/)
* **MapLibre GL JS UI:** [Popups and Lines](https://maplibre.org/maplibre-gl-js/docs/API/classes/Popup/)
* **Testing in ROS 2:** [pytest with rclpy](https://www.google.com/search?q=https://docs.ros.org/en/rolling/Tutorials/Intermediate/Testing/Python.html)
* **NiceGUI Async Integrations:** [NiceGUI documentation](https://nicegui.io/documentation)
* **Hardware Platform:** Open Farming Automation (OFA) System Architecture & ROS 2 Interfaces (internal institute documentation).

Here is the updated text for **Problem Statement 2**, adapted to explicitly require the integration of the geodetic transformation engine directly into the IPP software codebase.

## Problem Statement 2: IPP Integration of High-Precision Geodetic Transformations & Field RTK Validation

### Context & Motivation
For autonomous smart farming operations, sub-meter positioning errors can lead to crop damage or vehicle collisions. Consumer mapping engines utilize Web Mercator and WGS84, which do not account for continental drift (tectonic epochs) or local geoid undulations. To guarantee mission safety, the Intelligent Path Planner (IPP) software must be upgraded to natively and rigorously transform coordinates between the dynamic kinematic frame of live RTK streams (ITRF2020) and the static local Swiss coordinate frame (CH1903+/LV95 and LN02).

### Objectives & Tasks
The student will implement the underlying geodetic mathematics directly into the IPP backend, construct physical hardware testbenches, and conduct field validations using commercial UAVs to prove the planner's accuracy.

1. **IPP Software Integration & Transformation Engine:** Develop and integrate a precision geodetic transformation module directly into the IPP Python codebase. Utilizing `pyproj` and official Swisstopo grid shift files (`CHENyx06` for X/Y and `CHGeo2004` for Z undulation), the IPP backend must transparently convert user-defined Web Mercator map clicks into exact ITRF2020 (Current Epoch) 3D waypoints for routing, and vice versa for incoming ROS 2 robot telemetry.
2. **Hardware Testbench:** Configure simple RTK-capable receivers (e.g., u-blox F9P, Septentrio) receiving corrections from the Onocoy RTK service (or a personal radio-linked base station). The student will capture raw NMEA/RTCM data from the receivers to scientifically validate the mathematical accuracy of the IPP's newly integrated software transformations.
3. **UAV Field Validation:** Once the IPP's coordinate engine is sufficiently tested on the ground, the student will plan a full 3D mission within the IPP, export the generated waypoints, and upload them to a DJI Enterprise drone (e.g., DJI Matrice / Mavic Enterprise RTK). The student will execute the flight to physically verify the exactness of the IPP's terrain-following and planimetric precision in a real-world environment.

### Recommended Literature & Resources

* **Swisstopo Reference Frames:** [Swiss coordinate reference systems](https://www.google.com/search?q=https://www.swisstopo.admin.ch/en/knowledge-facts/surveying-geodesy/reference-frames.html)
* **PROJ & Grid Shifts:** [pyproj documentation](https://pyproj4.github.io/pyproj/stable/)
* **Onocoy RTK Service:** [Onocoy GNSS Network](https://www.onocoy.com/)
* **Hardware integration:** [u-blox ZED-F9P Integration Manual](https://www.u-blox.com/en/product/zed-f9p-module)

## Project Deliverables (Applicable to Both Topics)

1. **Software:** Fully functional, type-hinted Python and JavaScript code. All code must be committed to the institute's GitLab repository using a standard Git workflow.
2. **Hardware Configuration:** Detailed documentation of the robot setup, including sensors, actuators, communication hardware, etc.
3. **Documentation:** All software must be thoroughly documented with inline code comments and a comprehensive Markdown `README.md` containing installation and execution instructions, system diagrams, and a project plan (Gantt chart).
4. **Bachelor Thesis:** A concise academic report detailing the architecture, methodology, and results. **Maximum length: 30 pages.**


## Appendix: Thesis Writing Guidelines

To assist in writing a highly concise, professional thesis within the 30-page limit for main text, adhere to the following principles derived from top-tier Swiss technical institutes:

* **Brevity and Precision:** Scientific writing is direct. Avoid filler words, emotional language, and repetitive summaries. If a concept can be explained in one sentence, do not use a paragraph. Shorter, denser documents are graded higher than padded documents.
* **Diagrams Over Text:** Use standardized diagrams (e.g., UML, SysML, or Mermaid component diagrams) to explain software architectures and state machines. A well-constructed architecture diagram replaces pages of textual description. Reference the diagram directly in the text (e.g., *"As illustrated in Fig 2, the middleware decouples the..."*).
* **Strict Referencing:** Do not waste space explaining basic concepts (e.g., "What is GPS?" or "What is ROS 2?"). Instead, provide a one-sentence summary and immediately cite the primary source. Focus the page count strictly on *your* implementation, *your* problem-solving, and *your* results.

### Structure:

* *Abstract* (1/2 page max, write it last)
* *Introduction & Related Work* (2-3 pages write it during research phase)
* *Methodology / Architecture* (10-15 pages - core focus, write content during whole time)
* *Results & Validation* (5-8 pages - i.e. quantitative data, charts, rosbag outputs, variance plots and other experimental results)
* *Conclusion* (1 page, review your own work, issues remained open, successes failures. Don't mention that you hadn't enough time, nobody has.)

**Formatting Cleanliness:** Ensure all code snippets are placed in the appendix or linked via GitLab repositories rather than clogging the main text. Use clean, vector-based graphics for all plots and diagrams.

---

# Aufgabenstellungen für Bachelorarbeiten

**Forschungsgruppe:** Institut für Smart Farming (ISF)  
**Projekt:** Erweiterung des Intelligent Path Planners (IPP)

## Aufgabenstellung 1: ROS 2 Middleware & Ground Control UI mit OFA-Demonstration im Feld

### Kontext & Motivation

Der Intelligent Path Planner (IPP) ist ein webbasiertes 3D-Missionsplanungswerkzeug. Um den IPP von einer statischen Planungsanwendung in eine aktive Bodenstation (Ground Control Station, GCS) zu überführen, ist eine robuste Kommunikationsschicht erforderlich. Das System muss über die ROS 2 Middleware nativ mit einer heterogenen Flotte von unbemannten Bodenfahrzeugen (UGVs) und Fluggeräten (UAVs) interagieren. Den Abschluss der Arbeit bildet eine reale Demonstration im Feld mit der Open Farming Automation (OFA) Plattform, um die Praxistauglichkeit des Gesamtsystems nachzuweisen.

### Ziele & Aufgaben

Entwicklung einer asynchronen ROS 2 Bridge zwischen dem Python/NiceGUI-Backend und der Roboterflotte, Erweiterung des MapLibre GL JS Frontends um interaktive UI-Komponenten sowie die experimentelle Validierung im landwirtschaftlichen Umfeld.

1. **Middleware-Implementierung:** Aufbau einer ROS 2 Knotenarchitektur für bidirektionale Kommunikation. Roboter müssen ihren aktuellen Status und ihre Pose publizieren sowie Routenzuweisungen und Missionsparameter dynamisch über IPP-Topics (`/mission_data`) anfordern können.
2. **Interaktive UI-Erweiterung:** Erweiterung des Frontends. Beim Anklicken des 3D-Markers eines Roboters öffnet sich ein schwebendes Informationsfenster mit Live-Telemetriedaten. Eine dynamische, dünne Verbindungslinie verknüpft das UI-Fenster optisch mit dem Roboter auf dem Bildschirm, um die Übersichtlichkeit im Multi-Roboter-Betrieb zu wahren.
3. **Simulations- & Test-Pipeline:** Verifikation ohne physische Hardware über simulierte ROS 2 Datenquellen (Dummy Nodes). Erstellung automatisierter Unit-Tests sowie Testabläufe mittels ROS 2 Bag (`rosbag2`) Replays zur Analyse von Netzwerklatenz, Systemstabilität und UI-Reaktionszeiten.
4. **OFA-Demonstration im Feld:** Durchführung eines Praxistests mit dem Open Farming Automation (OFA) Roboter. Nachweis des geschlossenen Wirkungskreises: Generierung und Übertragung einer IPP-Abdeckungsroute, autonome Pfadabfahrt durch das OFA-Fahrzeug und kontinuierliche Live-Visualisierung der Telemetrie im Planner-Interface.

### Weiterführende Literatur & Quellen

* **ROS 2 Architektur:** [rclpy Dokumentation](https://docs.ros.org/en/rolling/p/rclpy/)
* **MapLibre GL JS UI:** [Popups and Lines](https://maplibre.org/maplibre-gl-js/docs/API/classes/Popup/)
* **Testen in ROS 2:** [pytest mit rclpy](https://www.google.com/search?q=https://docs.ros.org/en/rolling/Tutorials/Intermediate/Testing/Python.html)
* **NiceGUI Async-Integration:** [NiceGUI Dokumentation](https://nicegui.io/documentation)
* **Hardware-Plattform:** Open Farming Automation (OFA) Systemarchitektur & ROS 2 Schnittstellen (institutsinterne Dokumentation)

## Aufgabenstellung 2: IPP-Integration hochpräziser geodätischer Transformationen & RTK-Validierung im Feld

### Kontext & Motivation

In der autonomen Präzisionslandwirtschaft führen Positionierungsfehler im Submeterbereich zu Ernteverlusten oder Kollisionen. Standard-Webkarten basieren auf Web Mercator und WGS84 und vernachlässigen Kontinentaldrift (tektonische Epochen) sowie lokale Geoidundulationen. Der Intelligent Path Planner (IPP) muss daher um eine mathematisch exakte Transformation zwischen dem dynamisch-kinematischen Bezugsrahmen aktueller RTK-Korrekturdienste (ITRF2020) und dem statischen Schweizer Landeskoordinatensystem (CH1903+/LV95 und LN02) erweitert werden.

### Ziele & Aufgaben

Direkte Softwareintegration der geodätischen Rechenmodelle in das IPP-Backend, Aufbau eines GNSS-Prüfstands und flugbetriebliche Feldvalidierung mittels kommerzieller UAVs.

1. **Softwareintegration der Transformations-Engine:** Direkte Implementierung eines geodätischen Transformationsmoduls in die Python-Codebasis des IPP. Unter Nutzung von `pyproj` und den offiziellen Swisstopo-Gitterdateien (`CHENyx06` für Lageverschiebungen, `CHGeo2004` für Höhenundulationen) rechnet das Backend Klicks aus der Web-Mercator-Kartenansicht in ITRF2020-3D-Koordinaten um und transformiert eingehende ROS 2 Robotertelemetrie in das Schweizer Bezugssystem.
2. **Hardware-Prüfstand:** Konfiguration RTK-fähiger Empfänger (z. B. u-blox ZED-F9P, Septentrio) mit Anbindung an den Onocoy RTK-Korrekturdienst (oder eine lokale Basisstation via Funkverbindung). Aufzeichnung und Auswertung von NMEA/RTCM-Rohdaten zur messtechnischen Überprüfung der implementierten Algorithmen.
3. **UAV-Feldvalidierung:** Planung einer vollständigen 3D-Mission im IPP, Export der Wegpunkte und Import in eine DJI Enterprise Drohne (z. B. DJI Matrice / Mavic Enterprise RTK). Durchführung von Testflügen zur quantitativen Verifikation der Höhen- und Lagegenauigkeit bei der realen Geländeabformung.

### Weiterführende Literatur & Quellen

* **Swisstopo Bezugsrahmen:** [Geodätische Bezugssysteme der Schweiz](https://www.google.com/search?q=https://www.swisstopo.admin.ch/de/wissen-fakten/vermessung-geodesie/bezugsrahmen.html)
* **PROJ & Gittertransformationen:** [pyproj Dokumentation](https://pyproj4.github.io/pyproj/stable/)
* **Onocoy RTK-Netzwerk:** [Onocoy GNSS Network](https://www.onocoy.com/)
* **Hardware-Integration:** [u-blox ZED-F9P Integrationshandbuch](https://www.u-blox.com/en/product/zed-f9p-module)

## Projektergebnisse (Gültig für beide Themen)

1. **Software:** Voll funktionsfähiger, typisierter (type-hinted) Python- und JavaScript-Quellcode. Der gesamte Code muss nach einem Standard-Git-Workflow in das GitLab-Repository des Instituts übertragen (committed) werden.
2. **Hardware-Konfiguration:** Detaillierte Dokumentation des Roboter-Setups, einschliesslich Sensoren, Aktuatoren, Kommunikationshardware usw.
3. **Dokumentation:** Die gesamte Software muss durch Inline-Code-Kommentare sowie eine umfassende Markdown-Datei (`README.md`) sorgfältig dokumentiert werden. Diese muss Installations- und Ausführungsanweisungen, Systemdiagramme und einen Projektplan (Gantt-Diagramm) enthalten.
4. **Bachelorarbeit:** Ein prägnanter akademischer Bericht, der die Architektur, Methodik und Ergebnisse detailliert beschreibt. **Maximaler Umfang: 30 Seiten.**

## Anhang: Richtlinien zur Berichterstellung

Zur Einhaltung der 30-Seiten-Begrenzung und zur Wahrung eines hohen wissenschaftlichen Standards gelten folgende Richtlinien:

* **Prägnanz und Sachlichkeit:** Wissenschaftliche Texte sind dicht und frei von Füllwörtern. Redundante Zusammenfassungen und erzählerische Formulierungen sind zu vermeiden. Prägnante Aussagen werden höher bewertet als künstlich gestreckter Text.
* **Diagramme vor Text:** Softwarearchitekturen, Schnittstellen und Zustandsübergänge sind prioritär über standardisierte Diagramme (UML, SysML, Flowcharts) zu vermitteln. Ein präzises Architekturdiagramm ersetzt mehrere Textseiten. Jeder grafische Inhalt muss im Fliesstext explizit referenziert und kurz eingeordnet werden (*„Wie in Abb. 2 dargestellt, entkoppelt die Middleware...“*).
* **Fokussierte Zitierweise:** Elementare Grundlagenkonzepte (z. B. die generelle Funktionsweise von GNSS oder die Grundprinzipien von ROS 2) werden nicht seitenlang rekapituliert, sondern mit maximal einem prägnanten Satz zusammengefasst und direkt per Fachliteratur belegt. Der Platz gebührt ausschliesslich der *eigenen* Ingenieurleistung, der Implementierung und den Messergebnissen.

### Struktur:

* *Abstract* (max. 1/2 Seite, ganz am Schluss verfassen)
* *Einleitung & Verwandte Arbeiten* (2–3 Seiten, während der Recherchephase verfassen)
* *Methodik & Systemarchitektur* (10–15 Seiten – inhaltlicher Kern, Inhalte kontinuierlich während der gesamten Projektlaufzeit verfassen)
* *Ergebnisse & Validierung* (5–8 Seiten – d. h. quantitative Daten, Diagramme, Rosbag-Auswertungen, Varianz-Plots und weitere experimentelle Ergebnisse)
* *Schlussfolgerung / Fazit* (1 Seite, kritische Reflexion der eigenen Arbeit, offene Punkte, Erfolge und Misserfolge. Erwähnen Sie nicht, dass Sie zu wenig Zeit hatten – die hat niemand.)

**Code-Platzierung:** Quelltext gehört nicht in den Fliesstext. Relevante Schnittstellendefinitionen oder Konfigurationen sind in den Anhang auszulagern oder direkt auf den Commit im GitLab-Repository zu verweisen. Sämtliche Plots und Schemata sind als scharfe Vektorgrafiken (z. B. SVG/PDF) einzubinden.