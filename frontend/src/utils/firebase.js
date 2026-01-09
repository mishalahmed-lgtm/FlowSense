// Firebase configuration
import { initializeApp } from "firebase/app";
import { getFirestore, collection, doc, setDoc, getDoc, getDocs } from "firebase/firestore";

const firebaseConfig = {
  apiKey: "AIzaSyAZ39e477sCTQqhgsxXeIWCSo5ijGJh5xQ",
  authDomain: "flowset-143fc.firebaseapp.com",
  projectId: "flowset-143fc",
  storageBucket: "flowset-143fc.firebasestorage.app",
  messagingSenderId: "799211858991",
  appId: "1:799211858991:web:f7e63c89332e729fcdaada",
  measurementId: "G-HJ81T0FK9W"
};

// Initialize Firebase
const app = initializeApp(firebaseConfig);
export const db = getFirestore(app);

// Helper function to write "hello" to Firebase
export async function writeHelloToFirebase() {
  console.log("🔄 Starting Firebase write operation...");
  console.log("📝 Writing 'hello' to Firebase collection: 'demo_test'");
  
  try {
    const demoRef = doc(db, "demo_test", "hello");
    const data = {
      message: "hello",
      timestamp: new Date().toISOString(),
      created_at: new Date().toISOString()
    };
    
    console.log("📦 Data to write:", data);
    console.log("📍 Path: demo_test/hello");
    
    await setDoc(demoRef, data);
    
    console.log("✅ SUCCESS: Successfully wrote 'hello' to Firebase!");
    console.log("✅ Status: Write completed");
    console.log("✅ Location: demo_test/hello");
    return { success: true, message: "Write successful" };
  } catch (error) {
    console.error("❌ ERROR: Failed to write to Firebase");
    console.error("❌ Status: Write failed");
    console.error("❌ Error details:", error);
    console.error("❌ Error code:", error.code);
    console.error("❌ Error message:", error.message);
    return { success: false, error: error.message };
  }
}

// Helper function to read from Firebase
export async function readFromFirebase(path) {
  try {
    const docRef = doc(db, path);
    const docSnap = await getDoc(docRef);
    if (docSnap.exists()) {
      return docSnap.data();
    }
    return null;
  } catch (error) {
    console.error("❌ Error reading from Firebase:", error);
    return null;
  }
}

// Helper function to fetch installations data
export async function fetchInstallationsData() {
  console.log("🔄 Starting Firebase read operation...");
  console.log("📝 Reading from Firebase collection: 'installations'");
  
  try {
    const installationsRef = collection(db, "installations");
    
    console.log("📍 Path: installations");
    console.log("🔍 Fetching all documents...");
    
    const querySnapshot = await getDocs(installationsRef);
    
    console.log(`📊 Total documents found: ${querySnapshot.size}`);
    
    const installations = [];
    const deviceData = [];
    
    querySnapshot.forEach((docSnap) => {
      const data = docSnap.data();
      const docId = docSnap.id;
      
      console.log(`\n📄 Document ID: ${docId}`);
      console.log("📦 Document data:", data);
      
      // Extract device_id
      const deviceId = data.device_id || data.deviceId || data.id || docId;
      
      // Extract location details
      const location = data.location || data.loc || {};
      const latitude = location.latitude || location.lat || data.latitude || data.lat;
      const longitude = location.longitude || location.lng || data.longitude || data.lng;
      
      const installationInfo = {
        document_id: docId,
        device_id: deviceId,
        location: {
          latitude: latitude,
          longitude: longitude,
          full_location: location
        },
        raw_data: data
      };
      
      installations.push(installationInfo);
      deviceData.push({
        device_id: deviceId,
        latitude: latitude,
        longitude: longitude
      });
      
      console.log(`  ✅ Device ID: ${deviceId}`);
      console.log(`  📍 Location: lat=${latitude}, lng=${longitude}`);
    });
    
    console.log("\n" + "=".repeat(60));
    console.log("✅ SUCCESS: Successfully fetched installations data!");
    console.log("✅ Status: Read completed");
    console.log("✅ Total installations: " + querySnapshot.size);
    console.log("=".repeat(60));
    console.log("\n📋 Summary:");
    console.log(`  - Total devices: ${querySnapshot.size}`);
    console.log(`  - Devices with location: ${deviceData.filter(d => d.latitude && d.longitude).length}`);
    console.log(`  - Devices without location: ${deviceData.filter(d => !d.latitude || !d.longitude).length}`);
    
    console.log("\n📦 All Device Data:");
    deviceData.forEach((device, index) => {
      console.log(`  ${index + 1}. Device ID: ${device.device_id}, Location: (${device.latitude}, ${device.longitude})`);
    });
    
    console.log("\n" + "=".repeat(60));
    console.log("📋 ALL INSTALLATIONS DETAILED LIST:");
    console.log("=".repeat(60));
    installations.forEach((installation, index) => {
      console.log(`\n${index + 1}. Installation #${index + 1}:`);
      console.log(`   📄 Document ID: ${installation.document_id}`);
      console.log(`   🔌 Device ID: ${installation.device_id}`);
      console.log(`   📍 Location:`);
      console.log(`      - Latitude: ${installation.location.latitude || 'N/A'}`);
      console.log(`      - Longitude: ${installation.location.longitude || 'N/A'}`);
      console.log(`   📦 Full Location Object:`, installation.location.full_location);
      console.log(`   📊 Raw Data:`, installation.raw_data);
    });
    console.log("\n" + "=".repeat(60));
    console.log(`✅ Total Installations Printed: ${installations.length}`);
    console.log("=".repeat(60));
    
    return {
      success: true,
      total_devices: querySnapshot.size,
      installations: installations,
      device_data: deviceData
    };
  } catch (error) {
    console.error("❌ ERROR: Failed to read from Firebase");
    console.error("❌ Status: Read failed");
    console.error("❌ Error details:", error);
    console.error("❌ Error code:", error.code);
    console.error("❌ Error message:", error.message);
    return {
      success: false,
      error: error.message,
      total_devices: 0,
      installations: [],
      device_data: []
    };
  }
}

